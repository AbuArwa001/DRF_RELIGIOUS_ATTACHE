"""
DRF ViewSets for the competition app.
"""
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings as django_settings
from botocore.config import Config as BotocoreConfig

from .models import Category, Registration, CompetitionSettings
from .serializers import (
    CategorySerializer,
    CompetitionInfoSerializer,
    CompetitionInfoAdminSerializer,
    RegistrationCreateSerializer,
    RegistrationAdminSerializer,
)
from .permissions import IsAdminUser
from .validators import normalize_phone
from .emails import send_status_update_email

import io
import zipfile
from django.http import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/categories/       — list all categories
    GET /api/v1/categories/{id}/  — retrieve a single category
    Public endpoint, no authentication required.
    """
    queryset = Category.objects.all().order_by('order')
    serializer_class = CategorySerializer
    permission_classes = []  # fully public


class RegistrationViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,       # ← DELETE support
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST   /api/v1/registrations/              — public: submit registration (multipart)
    GET    /api/v1/registrations/              — admin: list all (supports ?search= query)
    GET    /api/v1/registrations/{id}/         — admin: retrieve one
    PUT    /api/v1/registrations/{id}/         — admin: full update
    PATCH  /api/v1/registrations/{id}/         — admin: partial update
    DELETE /api/v1/registrations/{id}/         — admin: delete entry
    PATCH  /api/v1/registrations/{id}/review/  — admin: update status + notes
    GET    /api/v1/registrations/{id}/photo_url/ — admin: get presigned S3 URL for passport photo
    GET    /api/v1/registrations/{id}/doc_url/   — admin: get presigned S3 URL for ID document
    """
    queryset = Registration.objects.select_related('category').all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['full_name', 'nominating_institution', 'phone_number', 'email', 'national_id_number']

    def get_serializer_class(self):
        if self.action == 'create':
            return RegistrationCreateSerializer
        return RegistrationAdminSerializer

    def get_permissions(self):
        if self.action in ['create', 'check_duplicate']:
            return []   # public registration submission and duplicate check
        return [IsAdminUser()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            RegistrationCreateSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Full update — admin can edit all editable fields."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_status = instance.status
        serializer = RegistrationAdminSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        if updated_instance.status in ['rejected', 'approved'] and old_status != updated_instance.status:
            send_status_update_email(updated_instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete a registration entry."""
        instance = self.get_object()
        instance.delete()
        return Response(
            {'detail': 'Registration deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT,
        )

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def review(self, request, pk=None):
        """
        PATCH /api/v1/registrations/{id}/review/
        Allows updating status and reviewer_notes only.
        """
        registration = self.get_object()
        old_status = registration.status
        allowed_fields = {'status', 'reviewer_notes'}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        serializer = RegistrationAdminSerializer(registration, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        if updated_instance.status in ['rejected', 'approved'] and old_status != updated_instance.status:
            send_status_update_email(updated_instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[], url_path='check_duplicate')
    def check_duplicate(self, request):
        """
        GET /api/v1/registrations/check_duplicate/?national_id=...&phone=...&email=...
        Public endpoint to check if a participant has already registered.
        """
        nat_id = (request.query_params.get('national_id') or '').strip()
        phone = (request.query_params.get('phone') or '').strip()
        email = (request.query_params.get('email') or '').strip()

        active_regs = Registration.objects.exclude(status=Registration.Status.REJECTED)

        nat_id_dup = bool(nat_id and active_regs.filter(national_id_number__iexact=nat_id).exists())

        phone_dup = False
        if phone:
            norm_phone = normalize_phone(phone)
            if norm_phone:
                existing_phones = active_regs.values_list('phone_number', flat=True)
                for ep in existing_phones:
                    if ep and normalize_phone(ep) == norm_phone:
                        phone_dup = True
                        break

        email_dup = bool(email and active_regs.filter(email__iexact=email).exists())

        return Response({
            'is_duplicate': nat_id_dup or phone_dup or email_dup,
            'fields': {
                'national_id': nat_id_dup,
                'phone': phone_dup,
                'email': email_dup,
            }
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser], url_path='bulk_download_pdfs')
    def bulk_download_pdfs(self, request):
        """
        POST /api/v1/registrations/bulk_download_pdfs/
        Body: {"ids": [1, 2, 3]}
        Generates a PDF for each selected registration and returns them in a ZIP archive.
        """
        ids = request.data.get('ids', [])
        if not ids or not isinstance(ids, list):
            return Response({'error': 'Please provide a list of registration IDs.'}, status=status.HTTP_400_BAD_REQUEST)
        
        registrations = Registration.objects.filter(id__in=ids).select_related('category')
        if not registrations.exists():
            return Response({'error': 'No registrations found for the provided IDs.'}, status=status.HTTP_404_NOT_FOUND)
        
        from pypdf import PdfWriter, PdfReader
        from datetime import datetime
        
        zip_buffer = io.BytesIO()
        
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        
        G = colors.HexColor('#0E7A4A')
        GD = colors.HexColor('#043823')
        
        section_title_style = ParagraphStyle(
            'SectionTitle', parent=normal_style, fontName='Helvetica-Bold', fontSize=10, textColor=colors.black,
            spaceAfter=8, spaceBefore=0, backColor=colors.HexColor('#F8FAFC'), borderPadding=(4, 4, 4, 4),
        )
        field_label_style = ParagraphStyle(
            'FieldLabel', parent=normal_style, fontName='Helvetica-Bold', fontSize=7, textColor=colors.gray,
        )
        field_value_style = ParagraphStyle(
            'FieldValue', parent=normal_style, fontName='Helvetica', fontSize=9, textColor=colors.black, spaceAfter=8,
        )
        
        def create_field(label, value):
            return [Paragraph(label.upper(), field_label_style), Paragraph(str(value) if value else "—", field_value_style)]

        now_str = datetime.now().strftime('%d %b %Y, %H:%M').upper()
        logo_path = '/home/khalfan/Desktop/ReligiousAttache/public/assets/Moi.jpg'

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for reg in registrations:
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer, 
                    pagesize=A4,
                    rightMargin=inch*0.5, leftMargin=inch*0.5,
                    topMargin=inch*0.5, bottomMargin=inch*0.5
                )
                elements = []
                
                # Header Table (Banner)
                try:
                    logo_img = RLImage(logo_path, width=0.8*inch, height=0.8*inch)
                except:
                    logo_img = Paragraph("LOGO", normal_style)
                
                cat_name = reg.category.name_en if reg.category else 'N/A'
                sub_date = reg.submitted_at.strftime("%d %B %Y")
                
                header_text = f"""
                <font color='#F0D97A' size=8><b>RELIGIOUS ATTACHÉ · SAUDI EMBASSY KENYA</b></font><br/>
                <font color='white' size=16><b>{reg.full_name}</b></font><br/>
                <font color='white' size=9>
                <font color='#F0D97A'>ID:</font> REF-{reg.id:05d} &nbsp;&nbsp;&nbsp;&nbsp; 
                <font color='#F0D97A'>Category:</font> {cat_name} &nbsp;&nbsp;&nbsp;&nbsp; 
                Submitted: {sub_date}
                </font>
                """
                header_p = Paragraph(header_text, ParagraphStyle('Header', fontName='Helvetica', leading=14))
                
                status_color = colors.HexColor('#D97706') if reg.status == 'pending' else colors.HexColor('#059669') if reg.status == 'approved' else colors.HexColor('#DC2626')
                status_bg = colors.HexColor('#FEF3C7') if reg.status == 'pending' else colors.HexColor('#ECFDF5') if reg.status == 'approved' else colors.HexColor('#FEF2F2')
                
                status_p = Paragraph(f"<font color='{status_color.hexval()}'><b>{reg.status.upper()}</b></font>", ParagraphStyle('Status', fontName='Helvetica-Bold', fontSize=8, alignment=1))
                status_table = Table([[status_p]], colWidths=[1*inch], rowHeights=[0.25*inch])
                status_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), status_bg),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ]))

                header_table = Table([[logo_img, header_p, status_table]], colWidths=[1*inch, 5*inch, 1.2*inch])
                header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), GD),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('VALIGN', (2,0), (2,0), 'TOP'),
                    ('TOPPADDING', (0,0), (-1,-1), 16),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 16),
                    ('LEFTPADDING', (0,0), (-1,-1), 16),
                    ('RIGHTPADDING', (0,0), (-1,-1), 16),
                ]))
                
                elements.append(header_table)
                elements.append(Spacer(1, 0.3*inch))
                
                # 2-Column Body Grid
                left_elements = []
                left_elements.append(Paragraph("👤 PERSONAL INFORMATION", section_title_style))
                left_elements.append(Spacer(1, 0.1*inch))
                
                personal_data = [
                    create_field("DATE OF BIRTH", reg.date_of_birth),
                    create_field("AGE", f"{reg.age} years old"),
                    create_field("NATIONALITY", reg.nationality),
                    create_field("NATIONAL ID / PASSPORT", reg.national_id_number),
                    create_field("CURRENT RESIDENCE", reg.current_residence),
                    create_field("HOME COUNTY", reg.county),
                ]
                p_table_data = []
                for i in range(0, len(personal_data), 2):
                    row = [personal_data[i]]
                    if i + 1 < len(personal_data): row.append(personal_data[i+1])
                    else: row.append([])
                    p_table_data.append(row)
                
                ptable = Table(p_table_data, colWidths=[2.3*inch, 2.3*inch])
                ptable.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
                left_elements.append(ptable)
                left_elements.append(Spacer(1, 0.2*inch))
                
                left_elements.append(Paragraph("📞 CONTACT & INSTITUTIONAL DATA", section_title_style))
                left_elements.append(Spacer(1, 0.1*inch))
                contact_data = [
                    create_field("PRIMARY PHONE", reg.phone_number),
                    create_field("ALTERNATIVE PHONE", reg.alternative_phone),
                    create_field("EMAIL ADDRESS", reg.email),
                    create_field("NOMINATING INSTITUTION", reg.nominating_institution),
                ]
                c_table_data = []
                for i in range(0, len(contact_data), 2):
                    row = [contact_data[i]]
                    if i + 1 < len(contact_data): row.append(contact_data[i+1])
                    else: row.append([])
                    c_table_data.append(row)
                
                ctable = Table(c_table_data, colWidths=[2.3*inch, 2.3*inch])
                ctable.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
                left_elements.append(ctable)
                
                right_elements = []
                right_elements.append(Paragraph("APPLICANT PHOTO", section_title_style))
                right_elements.append(Spacer(1, 0.1*inch))
                if reg.passport_photo:
                    try:
                        img_file = reg.passport_photo.open('rb')
                        img_data = io.BytesIO(img_file.read())
                        img = RLImage(img_data, width=1.5*inch, height=1.8*inch, kind='proportional')
                        img.hAlign = 'CENTER'
                        right_elements.append(img)
                        img_file.close()
                    except Exception as e:
                        right_elements.append(Paragraph(f"Could not load image: {e}", field_value_style))
                else:
                    right_elements.append(Paragraph("No photo attached", field_value_style))
                
                right_elements.append(Spacer(1, 0.2*inch))
                right_elements.append(Paragraph("ATTACHED DOCUMENTS", section_title_style))
                right_elements.append(Spacer(1, 0.1*inch))
                doc_text = "📄 National ID / Document<br/><font color='gray' size=8>See attached pages for secure PDF/Image</font>" if reg.id_document else "No ID document attached"
                right_elements.append(Paragraph(doc_text, normal_style))
                
                body_table = Table([[left_elements, right_elements]], colWidths=[4.7*inch, 2.5*inch])
                body_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ]))
                elements.append(body_table)
                
                elements.append(Spacer(1, 1*inch))
                elements.append(Paragraph(f"<font color='gray' size=7><b>OFFICIAL QURAN COMPETITION 2026 REGISTRY</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; GENERATED: {now_str}</font>", ParagraphStyle('Footer', alignment=0)))
                
                doc.build(elements)
                
                # Merge ID document
                reportlab_pdf_bytes = pdf_buffer.getvalue()
                writer = PdfWriter()
                
                reader1 = PdfReader(io.BytesIO(reportlab_pdf_bytes))
                for page in reader1.pages:
                    writer.add_page(page)
                
                if reg.id_document:
                    try:
                        id_file = reg.id_document.open('rb')
                        id_data = io.BytesIO(id_file.read())
                        filename_lower = reg.id_document.name.lower()
                        
                        if filename_lower.endswith('.pdf'):
                            id_reader = PdfReader(id_data)
                            for page in id_reader.pages:
                                writer.add_page(page)
                        elif filename_lower.endswith(('.jpg', '.jpeg', '.png')):
                            img_pdf_buffer = io.BytesIO()
                            img_doc = SimpleDocTemplate(
                                img_pdf_buffer, pagesize=A4, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch
                            )
                            img_elements = []
                            img_elements.append(Paragraph("ATTACHED IDENTIFICATION DOCUMENT", section_title_style))
                            img_elements.append(Spacer(1, 0.5*inch))
                            id_img = RLImage(id_data, width=6*inch, height=8*inch, kind='proportional')
                            img_elements.append(id_img)
                            img_doc.build(img_elements)
                            
                            id_reader = PdfReader(io.BytesIO(img_pdf_buffer.getvalue()))
                            for page in id_reader.pages:
                                writer.add_page(page)
                        id_file.close()
                    except Exception as e:
                        print(f"Error appending ID document for reg {reg.id}: {e}")
                
                merged_pdf_buffer = io.BytesIO()
                writer.write(merged_pdf_buffer)
                merged_pdf_bytes = merged_pdf_buffer.getvalue()
                
                safe_name = "".join([c for c in reg.full_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                filename = f"Candidate_{reg.id}_{safe_name.replace(' ', '_')}.pdf"
                zip_file.writestr(filename, merged_pdf_bytes)
        
        zip_buffer.seek(0)
        return FileResponse(zip_buffer, as_attachment=True, filename='candidate-registrations.zip')

    # ── S3 helper ──────────────────────────────────────────────────────────
    @staticmethod
    def _make_s3_client():
        """
        Return a boto3 S3 client configured to sign requests with
        AWS Signature Version 4 (SigV4 / AWS4-HMAC-SHA256).
        Many newer S3 buckets and regions reject the legacy SigV2 format.
        """
        import boto3
        return boto3.client(
            's3',
            aws_access_key_id=django_settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=django_settings.AWS_SECRET_ACCESS_KEY,
            region_name=django_settings.AWS_S3_REGION_NAME,
            config=BotocoreConfig(signature_version='s3v4'),   # ← SigV4
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser], url_path='photo_url')
    def photo_url(self, request, pk=None):
        """
        GET /api/v1/registrations/{id}/photo_url/
        Returns a short-lived (5-minute) presigned S3 URL for the passport photo.
        Falls back to an absolute media URL in local dev.
        """
        registration = self.get_object()
        if not registration.passport_photo:
            return Response({'url': None})

        if getattr(django_settings, 'USE_S3', False):
            try:
                s3  = self._make_s3_client()
                url = s3.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': django_settings.AWS_STORAGE_BUCKET_NAME,
                        'Key':    registration.passport_photo.name,
                    },
                    ExpiresIn=300,   # 5 minutes
                )
                return Response({'url': url})
            except Exception as e:
                return Response({'url': None, 'error': str(e)}, status=500)

        # Local dev fallback
        url = request._request.build_absolute_uri(registration.passport_photo.url)
        return Response({'url': url})

    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser], url_path='doc_url')
    def doc_url(self, request, pk=None):
        """
        GET /api/v1/registrations/{id}/doc_url/
        Returns a short-lived (5-minute) presigned S3 URL for the ID document.
        Falls back to an absolute media URL in local dev.
        """
        registration = self.get_object()
        if not registration.id_document:
            return Response({'url': None})

        if getattr(django_settings, 'USE_S3', False):
            try:
                s3  = self._make_s3_client()
                url = s3.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': django_settings.AWS_STORAGE_BUCKET_NAME,
                        'Key':    registration.id_document.name,
                    },
                    ExpiresIn=300,   # 5 minutes
                )
                return Response({'url': url})
            except Exception as e:
                return Response({'url': None, 'error': str(e)}, status=500)

        # Local dev fallback
        url = request._request.build_absolute_uri(registration.id_document.url)
        return Response({'url': url})


class CompetitionInfoView(APIView):
    """
    GET    /api/v1/info/  — public: returns competition dates, venue, about text.
    PUT    /api/v1/info/  — admin: full update of all settings fields.
    PATCH  /api/v1/info/  — admin: partial update (only supplied fields are changed).
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return []           # public read
        return [IsAdminUser()]  # all writes require admin JWT

    def get(self, request):
        """Return the current competition settings (public)."""
        settings = CompetitionSettings.load()
        serializer = CompetitionInfoSerializer(settings)
        return Response(serializer.data)

    def put(self, request):
        """Full update — all fields must be supplied."""
        settings = CompetitionSettings.load()
        serializer = CompetitionInfoAdminSerializer(settings, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        """Partial update — only the supplied fields are changed."""
        settings = CompetitionSettings.load()
        serializer = CompetitionInfoAdminSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
