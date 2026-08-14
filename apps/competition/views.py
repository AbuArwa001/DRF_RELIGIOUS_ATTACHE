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
        email = str(request.data.get('email', '')).strip().lower()
        if email:
            from django.core.cache import cache
            from django.utils.translation import gettext as _
            lock_key = f"registration_lock_{email}"
            if not cache.add(lock_key, 'locked', 10):
                return Response(
                    {"email": [_("A registration with this email is currently being processed. Please wait.")]},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return Response(
                RegistrationCreateSerializer(instance).data,
                status=status.HTTP_201_CREATED,
            )
        except Exception:
            if email:
                cache.delete(lock_key)
            raise

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
        email_dup = bool(email and active_regs.filter(email__iexact=email).exists())

        return Response({
            'is_duplicate': nat_id_dup or email_dup,
            'fields': {
                'national_id': nat_id_dup,
                'phone': False,
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
        
        from weasyprint import HTML
        import base64
        
        zip_buffer = io.BytesIO()
        
        now_str = datetime.now().strftime('%d AUG %Y, %H:%M').upper()
        
        import urllib.request
        try:
            req = urllib.request.Request("https://www.religiousattacheksa.co.ke/assets/Moi.jpg", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                logo_b64 = base64.b64encode(response.read()).decode("utf-8")
                logo_data_uri = f"data:image/jpeg;base64,{logo_b64}"
        except Exception as e:
            print(f"Error fetching logo: {e}")
            logo_data_uri = ""
            
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for reg in registrations:
                cat_name = reg.category.name_en if reg.category else 'N/A'
                sub_date = reg.submitted_at.strftime("%d %B %Y")
                
                status_color = '#D97706' if reg.status == 'pending' else '#059669' if reg.status == 'approved' else '#DC2626'
                status_bg = '#FEF3C7' if reg.status == 'pending' else '#ECFDF5' if reg.status == 'approved' else '#FEF2F2'
                
                photo_html = "<div style='color: #6B7280; font-size: 12px; margin-top: 50px;'>No photo attached</div>"
                if reg.passport_photo:
                    try:
                        img_file = reg.passport_photo.open('rb')
                        img_b64 = base64.b64encode(img_file.read()).decode("utf-8")
                        img_ext = reg.passport_photo.name.split('.')[-1].lower()
                        mime = "image/png" if img_ext == "png" else "image/jpeg"
                        photo_html = f'<img src="data:{mime};base64,{img_b64}" />'
                        img_file.close()
                    except:
                        pass
                
                doc_html = "<div style='color: #6B7280; font-size: 12px;'>No ID document attached</div>"
                if reg.id_document:
                    doc_html = """
                    <div class="document-card">
                      <div class="document-icon">
                        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M7 18H17V16H7V18ZM7 14H17V12H7V14ZM7 10H14V8H7V10ZM3 22V2H15L21 8V22H3ZM14 9H19.5L14 3.5V9Z" fill="currentColor"/>
                        </svg>
                      </div>
                      <div class="document-info">
                        <div class="doc-title">National ID /<br/>Document</div>
                        <div class="doc-desc">Click to view secure PDF/<br/>Image</div>
                      </div>
                    </div>
                    """
                
                date_of_birth_str = reg.date_of_birth.strftime('%d %B %Y') if reg.date_of_birth else "—"
                
                html_string = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <meta charset="UTF-8">
                <style>
                  @page {{
                    size: A4;
                    margin: 0;
                  }}
                  body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    margin: 10mm;
                    color: #111827;
                  }}
                  .card {{
                    border: 1px solid #E5E7EB;
                    border-radius: 6px;
                    overflow: hidden;
                    background: #FFFFFF;
                  }}
                  .header {{
                    background: #0E7A4A;
                    background-image: url('data:image/svg+xml;utf8,<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><path d="M10 10h10v10H10z" fill="rgba(255,255,255,0.02)"/></svg>');
                    padding: 24px 32px;
                    display: table;
                    width: 100%;
                    box-sizing: border-box;
                    border-bottom: 2px solid #043823;
                  }}
                  .header-logo-cell {{
                    display: table-cell;
                    vertical-align: top;
                    width: 80px;
                  }}
                  .header-logo {{
                    width: 70px;
                    height: 70px;
                    border-radius: 50%;
                    background-color: white;
                    object-fit: cover;
                    border: 2px solid #F0D97A;
                  }}
                  .header-content-cell {{
                    display: table-cell;
                    vertical-align: top;
                    padding-left: 16px;
                  }}
                  .header-title {{
                    color: #F0D97A;
                    font-size: 10px;
                    font-weight: 800;
                    letter-spacing: 1px;
                    margin-bottom: 6px;
                    text-transform: uppercase;
                  }}
                  .header-name {{
                    color: white;
                    font-size: 20px;
                    font-weight: 800;
                    margin: 0 0 8px 0;
                  }}
                  .header-meta {{
                    color: #E2E8F0;
                    font-size: 11px;
                    font-weight: 600;
                  }}
                  .header-meta span {{
                    color: #F0D97A;
                    font-weight: 800;
                  }}
                  .header-badge-cell {{
                    display: table-cell;
                    vertical-align: top;
                    text-align: right;
                    width: 120px;
                  }}
                  .status-badge {{
                    display: inline-block;
                    background-color: {status_bg};
                    color: {status_color};
                    padding: 6px 14px;
                    border-radius: 20px;
                    font-weight: 800;
                    font-size: 10px;
                    text-transform: uppercase;
                    margin-top: 4px;
                  }}
                  .grid-container {{
                    display: table;
                    width: 100%;
                    padding: 24px;
                    box-sizing: border-box;
                    table-layout: fixed;
                  }}
                  .col-left {{
                    display: table-cell;
                    width: 60%;
                    padding-right: 24px;
                    vertical-align: top;
                  }}
                  .col-right {{
                    display: table-cell;
                    width: 40%;
                    vertical-align: top;
                  }}
                  .section {{
                    border: 1px solid #F3F4F6;
                    border-radius: 12px;
                    background: #F9FAFB;
                    margin-bottom: 20px;
                  }}
                  .section-header {{
                    padding: 16px 20px;
                    font-size: 12px;
                    font-weight: 800;
                    color: #111827;
                    border-bottom: 1px solid #F3F4F6;
                    background: #FFFFFF;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                  }}
                  .section-content {{
                    padding: 20px;
                  }}
                  .field {{
                    margin-bottom: 16px;
                  }}
                  .field:last-child {{
                    margin-bottom: 0;
                  }}
                  .field-label {{
                    font-size: 9px;
                    color: #6B7280;
                    font-weight: 800;
                    text-transform: uppercase;
                    margin-bottom: 6px;
                    letter-spacing: 0.5px;
                  }}
                  .field-value {{
                    font-size: 13px;
                    color: #111827;
                    font-weight: 700;
                  }}
                  .photo-container {{
                    text-align: center;
                    background: #FFFFFF;
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                    padding-bottom: 20px;
                    padding-top: 10px;
                  }}
                  .photo-container img {{
                    width: 120px;
                    height: 150px;
                    object-fit: cover;
                    border-radius: 8px;
                    border: 1px dashed #D1D5DB;
                    padding: 4px;
                    background: white;
                  }}
                  .document-card {{
                    background: #F9FAFB;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 12px;
                    display: table;
                    width: 100%;
                    box-sizing: border-box;
                  }}
                  .document-icon {{
                    display: table-cell;
                    width: 36px;
                    height: 36px;
                    background: #EFF6FF;
                    border-radius: 6px;
                    vertical-align: middle;
                    text-align: center;
                  }}
                  .document-icon svg {{
                    width: 18px;
                    height: 18px;
                    color: #3B82F6;
                    display: inline-block;
                    margin-top: 8px;
                  }}
                  .document-info {{
                    display: table-cell;
                    vertical-align: middle;
                    padding-left: 12px;
                  }}
                  .document-info .doc-title {{
                    font-size: 11px;
                    font-weight: 800;
                    margin-bottom: 4px;
                    color: #111827;
                  }}
                  .document-info .doc-desc {{
                    font-size: 10px;
                    color: #6B7280;
                  }}
                  .footer {{
                    margin-top: 10px;
                    padding: 12px 24px;
                    background: #F8FAFC;
                    font-size: 9px;
                    color: #9CA3AF;
                    display: table;
                    width: 100%;
                    box-sizing: border-box;
                    border-top: 1px solid #E5E7EB;
                  }}
                  .footer .left {{
                    display: table-cell;
                    font-weight: 800;
                    text-transform: uppercase;
                    text-align: left;
                  }}
                  .footer .right {{
                    display: table-cell;
                    text-transform: uppercase;
                    text-align: right;
                    font-weight: 600;
                  }}
                </style>
                </head>
                <body>
                  <div class="card">
                    <div class="header">
                      <div class="header-logo-cell">
                        <img src="{logo_data_uri}" class="header-logo" />
                      </div>
                      <div class="header-content-cell">
                        <div class="header-title">RELIGIOUS ATTACHÉ · SAUDI EMBASSY KENYA</div>
                        <h1 class="header-name">{reg.full_name}</h1>
                        <div class="header-meta">
                          <span>ID:</span> REF-{reg.id:05d} &nbsp;&nbsp;•&nbsp;&nbsp; 
                          <span>Category:</span> {cat_name} &nbsp;&nbsp;•&nbsp;&nbsp; 
                          <span>Submitted:</span> {sub_date}
                        </div>
                      </div>
                      <div class="header-badge-cell">
                        <div class="status-badge">
                          <span style="color: {status_color}; font-size: 14px; vertical-align: middle; line-height: 0;">•</span> {reg.status}
                        </div>
                      </div>
                    </div>
                    
                    <div class="grid-container">
                      <div class="col-left">
                        <!-- Personal Information -->
                        <div class="section" style="background: #FFFFFF;">
                          <div class="section-header" style="background: #F9FAFB; border-bottom: none;">
                            <span style="color: #3B82F6; font-size: 14px; margin-right: 8px;">👤</span>
                            PERSONAL INFORMATION
                          </div>
                          <div class="section-content" style="background: #FFFFFF; border-top: 1px solid #F3F4F6;">
                            <div class="field">
                              <div class="field-label">DATE OF BIRTH</div>
                              <div class="field-value">{date_of_birth_str}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">AGE</div>
                              <div class="field-value">{reg.age} years old</div>
                            </div>
                            <div class="field">
                              <div class="field-label">NATIONALITY</div>
                              <div class="field-value">{reg.nationality}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">NATIONAL ID / PASSPORT</div>
                              <div class="field-value">{reg.national_id_number}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">CURRENT RESIDENCE</div>
                              <div class="field-value">{reg.current_residence}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">HOME COUNTY</div>
                              <div class="field-value">{reg.county}</div>
                            </div>
                          </div>
                        </div>

                        <!-- Contact & Institutional Data -->
                        <div class="section" style="background: #FFFFFF;">
                          <div class="section-header" style="background: #F9FAFB; border-bottom: none;">
                            <span style="color: #4B5563; font-size: 14px; margin-right: 8px;">📞</span>
                            CONTACT & INSTITUTIONAL DATA
                          </div>
                          <div class="section-content" style="background: #FFFFFF; border-top: 1px solid #F3F4F6;">
                            <div class="field">
                              <div class="field-label">PRIMARY PHONE</div>
                              <div class="field-value">{reg.phone_number}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">ALTERNATIVE PHONE</div>
                              <div class="field-value">{reg.alternative_phone or "—"}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">EMAIL ADDRESS</div>
                              <div class="field-value">{reg.email or "—"}</div>
                            </div>
                            <div class="field">
                              <div class="field-label">NOMINATING INSTITUTION</div>
                              <div class="field-value">{reg.nominating_institution}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div class="col-right">
                        <!-- Applicant Photo -->
                        <div class="section" style="background: #FFFFFF;">
                          <div class="section-header" style="background: #FFFFFF; border-bottom: none; text-align: center;">
                            APPLICANT PHOTO
                          </div>
                          <div class="section-content photo-container">
                            {photo_html}
                          </div>
                        </div>

                        <!-- Attached Documents -->
                        <div class="section" style="background: #FFFFFF;">
                          <div class="section-header" style="background: #FFFFFF; border-bottom: none;">
                            ATTACHED DOCUMENTS
                          </div>
                          <div class="section-content">
                            {doc_html}
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div class="footer">
                      <div class="left">OFFICIAL QURAN COMPETITION 2026 REGISTRY</div>
                      <div class="right">GENERATED: {now_str}</div>
                    </div>
                  </div>
                </body>
                </html>
                """
                weasyprint_pdf_bytes = HTML(string=html_string).write_pdf()
                
                # Merge ID document
                writer = PdfWriter()
                
                reader1 = PdfReader(io.BytesIO(weasyprint_pdf_bytes))
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
                            styles = getSampleStyleSheet()
                            normal_style = styles['Normal']
                            section_title_style = ParagraphStyle(
                                'SectionTitle', parent=normal_style, fontName='Helvetica-Bold', fontSize=10, textColor=colors.black,
                                spaceAfter=8, spaceBefore=0, backColor=colors.HexColor('#F8FAFC'), borderPadding=(4, 4, 4, 4),
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
