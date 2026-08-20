"""
DRF ViewSets for the competition app.
"""
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings as django_settings
from botocore.config import Config as BotocoreConfig

from .models import Category, Registration, CompetitionSettings, AuditLog
from .serializers import (
    CategorySerializer,
    CompetitionInfoSerializer,
    CompetitionInfoAdminSerializer,
    RegistrationCreateSerializer,
    RegistrationAdminSerializer,
    AuditLogSerializer,
)
from .permissions import IsAdminUser
from .emails import (
    send_status_update_email,
    send_category_update_email,
    send_profile_update_email,
)

import io
import zipfile
import xlsxwriter
from django.db.models import Count
from django.http import FileResponse, HttpResponse
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

    from django.utils.decorators import method_decorator
    from django.views.decorators.cache import cache_page

    @method_decorator(cache_page(60 * 60 * 24))  # Cache for 24 hours
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


_CACHED_LOGO_DATA_URI = None


def get_logo_data_uri():
    global _CACHED_LOGO_DATA_URI
    if _CACHED_LOGO_DATA_URI is not None:
        return _CACHED_LOGO_DATA_URI

    import urllib.request
    import base64
    try:
        req = urllib.request.Request(
            "https://www.religiousattacheksa.co.ke/assets/Moi.jpg",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            logo_b64 = base64.b64encode(response.read()).decode("utf-8")
            _CACHED_LOGO_DATA_URI = f"data:image/jpeg;base64,{logo_b64}"
    except Exception as e:
        print(f"Error fetching logo: {e}")
        _CACHED_LOGO_DATA_URI = ""
    return _CACHED_LOGO_DATA_URI


def generate_registration_pdf(reg, logo_data_uri=None):
    """
    Compiles a comprehensive dossier PDF for a single Registration record,
    rendering official styling and merging any attached ID document (PDF or image).
    Returns the final merged PDF bytes.
    """
    from pypdf import PdfWriter, PdfReader
    from datetime import datetime
    from weasyprint import HTML
    import base64

    if logo_data_uri is None:
        logo_data_uri = get_logo_data_uri()

    now_str = datetime.now().strftime('%d AUG %Y, %H:%M').upper()
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
        except Exception as e:
            print(f"Error reading passport photo for reg {reg.id}: {e}")

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
                img_elements.append(Spacer(1, 0.5 * inch))
                id_img = RLImage(id_data, width=6 * inch, height=8 * inch, kind='proportional')
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
    return merged_pdf_buffer.getvalue()


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
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            
            # Invalidate public competition info cache to update stats instantly
            from django.core.cache import cache
            cache.delete('competition_info_public')
            
            AuditLog.objects.create(
                action='CREATE',
                module='Registration',
                record_id=instance.id,
                record_name=instance.full_name,
                ip_address=request.META.get('REMOTE_ADDR'),
                details={"message": "New registration submitted publicly"}
            )
            
            return Response(
                RegistrationCreateSerializer(instance).data,
                status=status.HTTP_201_CREATED,
            )
        except Exception:
            raise

    def update(self, request, *args, **kwargs):
        """Full or partial update — admin can edit all editable fields, including photo and details."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Snapshot old values
        old_status = instance.status
        old_full_name = instance.full_name
        old_institution = instance.nominating_institution
        old_email = instance.email
        old_phone = instance.phone_number
        old_alt_phone = instance.alternative_phone
        old_dob = instance.date_of_birth
        old_county = instance.county
        old_nat_id = instance.national_id_number
        old_category_id = instance.category_id
        old_category_name = instance.category.name_en if instance.category else None
        old_photo_name = instance.passport_photo.name if instance.passport_photo else None
        old_doc_name = instance.id_document.name if instance.id_document else None

        serializer = RegistrationAdminSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()

        # Invalidate public stats cache if category or county changed
        if old_category_id != updated_instance.category_id or old_county != updated_instance.county:
            from django.core.cache import cache
            cache.delete('competition_info_public')

        # Detect changed fields
        changed_fields = {}
        if old_full_name != updated_instance.full_name:
            changed_fields['full_name'] = {'label': 'Full Name', 'old': old_full_name, 'new': updated_instance.full_name}
        if old_institution != updated_instance.nominating_institution:
            changed_fields['nominating_institution'] = {'label': 'Nominating Institution', 'old': old_institution, 'new': updated_instance.nominating_institution}
        if old_email != updated_instance.email:
            changed_fields['email'] = {'label': 'Email Address', 'old': old_email, 'new': updated_instance.email}
        if old_phone != updated_instance.phone_number:
            changed_fields['phone_number'] = {'label': 'Phone Number', 'old': old_phone, 'new': updated_instance.phone_number}
        if old_alt_phone != updated_instance.alternative_phone:
            changed_fields['alternative_phone'] = {'label': 'Alternative Phone', 'old': old_alt_phone, 'new': updated_instance.alternative_phone}
        if old_dob != updated_instance.date_of_birth:
            changed_fields['date_of_birth'] = {'label': 'Date of Birth', 'old': str(old_dob), 'new': str(updated_instance.date_of_birth)}
        if old_county != updated_instance.county:
            changed_fields['county'] = {'label': 'County', 'old': old_county, 'new': updated_instance.county}
        if old_nat_id != updated_instance.national_id_number:
            changed_fields['national_id_number'] = {'label': 'National ID / Passport', 'old': old_nat_id, 'new': updated_instance.national_id_number}
        if old_category_id != updated_instance.category_id:
            changed_fields['category'] = {'label': 'Memorization Category', 'old': old_category_name or 'Unassigned', 'new': updated_instance.category.name_en if updated_instance.category else 'Unassigned'}
        if ('passport_photo' in request.FILES) or (updated_instance.passport_photo and updated_instance.passport_photo.name != old_photo_name):
            changed_fields['passport_photo'] = {'label': 'Passport Photo', 'old': 'Previous Photo', 'new': 'Updated Photo'}
        if ('id_document' in request.FILES) or (updated_instance.id_document and updated_instance.id_document.name != old_doc_name):
            changed_fields['id_document'] = {'label': 'ID Document', 'old': 'Previous Document', 'new': 'Updated Document'}

        send_email_flag = request.data.get('send_email', True)
        if isinstance(send_email_flag, str):
            send_email_flag = send_email_flag.lower() in ('true', '1', 'yes')

        email_sent = False
        reason = (request.data.get('reason') or request.data.get('reviewer_notes') or '').strip()

        if send_email_flag:
            # If profile details changed, send profile update email
            if changed_fields:
                extra_recipients = [old_email] if (old_email and old_email != updated_instance.email) else None
                email_sent = send_profile_update_email(
                    registration=updated_instance,
                    changed_fields=changed_fields,
                    reason=reason,
                    extra_recipients=extra_recipients,
                )
            # If ONLY status changed and no profile details changed
            elif updated_instance.status in ['rejected', 'approved'] and old_status != updated_instance.status:
                email_sent = send_status_update_email(updated_instance)

        AuditLog.objects.create(
            user=request.user.username if request.user and request.user.is_authenticated else None,
            action='UPDATE',
            module='Registration',
            record_id=updated_instance.id,
            record_name=updated_instance.full_name,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"changed_fields": changed_fields, "reason": reason}
        )

        response_data = serializer.data
        response_data['email_sent'] = email_sent
        return Response(response_data)

    def destroy(self, request, *args, **kwargs):
        """Delete a registration entry."""
        instance = self.get_object()
        record_name = instance.full_name
        instance.delete()
        
        AuditLog.objects.create(
            user=request.user.username if request.user and request.user.is_authenticated else None,
            action='DELETE',
            module='Registration',
            record_name=record_name,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={"message": "Registration was deleted"}
        )
        
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
            
        AuditLog.objects.create(
            user=request.user.username if request.user and request.user.is_authenticated else None,
            action='UPDATE',
            module='Registration',
            record_id=updated_instance.id,
            record_name=updated_instance.full_name,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={
                "changed_fields": {
                    "status": {"old": old_status, "new": updated_instance.status},
                },
                "notes_updated": "reviewer_notes" in data
            }
        )
            
        return Response(serializer.data)

    @action(detail=True, methods=['post', 'patch'], permission_classes=[IsAdminUser], url_path='change_category')
    def change_category(self, request, pk=None):
        """
        POST/PATCH /api/v1/registrations/{id}/change_category/
        Body: {
            "category": 2,          # or "category_id": 2
            "reason": "Optional note",
            "send_email": true      # optional boolean, default: True
        }
        Updates the participant's memorization category and sends an email notification.
        """
        registration = self.get_object()
        category_id = request.data.get('category') or request.data.get('category_id')
        if not category_id:
            return Response({'error': 'Please provide a valid category ID.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            return Response({'error': 'The specified category does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        old_category_name = registration.category.name_en if registration.category else "Unassigned"
        reason = (request.data.get('reason') or '').strip()
        send_email_flag = request.data.get('send_email', True)
        if isinstance(send_email_flag, str):
            send_email_flag = send_email_flag.lower() in ('true', '1', 'yes')

        registration.category = new_category
        if reason:
            existing_notes = registration.reviewer_notes or ""
            note_entry = f"[Category changed to {new_category.name_en}]: {reason}"
            registration.reviewer_notes = f"{existing_notes}\n{note_entry}".strip() if existing_notes else note_entry

        registration.save(update_fields=['category', 'reviewer_notes', 'updated_at'])

        # Invalidate stats cache
        from django.core.cache import cache
        cache.delete('competition_info_public')

        email_sent = False
        if send_email_flag:
            email_sent = send_category_update_email(
                registration=registration,
                old_category_name=old_category_name,
                new_category_name=new_category.name_en,
                reason=reason,
            )

        AuditLog.objects.create(
            user=request.user.username if request.user and request.user.is_authenticated else None,
            action='UPDATE',
            module='Registration',
            record_id=registration.id,
            record_name=registration.full_name,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={
                "changed_fields": {
                    "category": {"old": old_category_name, "new": new_category.name_en}
                },
                "reason": reason
            }
        )

        serializer = RegistrationAdminSerializer(registration)
        return Response({
            **serializer.data,
            'email_sent': email_sent,
            'message': f"Participant category changed to {new_category.name_en} successfully."
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser], url_path='export_analysis')
    def export_analysis(self, request):
        """
        GET /api/v1/registrations/export_analysis/?pivot=category|county|status
        Generates an Excel file with pivot charts and raw data.
        """
        pivot = request.query_params.get('pivot', 'category').lower()
        if pivot not in ['category', 'county', 'status']:
            pivot = 'category'
            
        pivot_field = 'category__name_en' if pivot == 'category' else pivot
        
        registrations = self.get_queryset()
        pivot_data = registrations.values(pivot_field).annotate(count=Count('id')).order_by('-count')
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        header_format = workbook.add_format({'bold': True, 'bg_color': '#0E7A4A', 'font_color': 'white'})
        
        # --- Sheet 1: Dashboard ---
        dashboard_sheet = workbook.add_worksheet('Dashboard')
        dashboard_sheet.set_column('A:A', 25)
        dashboard_sheet.set_column('B:B', 15)
        
        dashboard_sheet.write('A1', f'Pivot by {pivot.capitalize()}', header_format)
        dashboard_sheet.write('B1', 'Count', header_format)
        
        row = 1
        for item in pivot_data:
            label = item[pivot_field] or 'Unknown'
            dashboard_sheet.write(row, 0, str(label))
            dashboard_sheet.write(row, 1, item['count'])
            row += 1
            
        chart = workbook.add_chart({'type': 'pie'})
        chart.add_series({
            'name': f'Registrations by {pivot.capitalize()}',
            'categories': ['Dashboard', 1, 0, row - 1, 0],
            'values': ['Dashboard', 1, 1, row - 1, 1],
            'data_labels': {'value': True, 'percentage': True},
        })
        chart.set_title({'name': f'Registration Distribution ({pivot.capitalize()})'})
        chart.set_style(10)
        chart.set_size({'width': 600, 'height': 400})
        dashboard_sheet.insert_chart('D2', chart)
        
        # --- Sheet 2: Raw Data ---
        raw_sheet = workbook.add_worksheet('Raw Data')
        columns = [
            'ID', 'Full Name', 'Category', 'Age', 'County', 'Status', 
            'Nominating Institution', 'Phone', 'Email', 'Submitted At'
        ]
        for col_num, column_title in enumerate(columns):
            raw_sheet.write(0, col_num, column_title, header_format)
            
        raw_sheet.set_column('A:A', 10)
        raw_sheet.set_column('B:B', 30)
        raw_sheet.set_column('C:C', 20)
        raw_sheet.set_column('E:E', 20)
        raw_sheet.set_column('G:G', 30)
        raw_sheet.set_column('H:J', 25)
        
        row = 1
        for reg in registrations.select_related('category'):
            raw_sheet.write(row, 0, f"REF-{reg.id:05d}")
            raw_sheet.write(row, 1, reg.full_name)
            raw_sheet.write(row, 2, reg.category.name_en if reg.category else 'N/A')
            raw_sheet.write(row, 3, reg.age or 'N/A')
            raw_sheet.write(row, 4, reg.county or 'N/A')
            raw_sheet.write(row, 5, reg.status.upper())
            raw_sheet.write(row, 6, reg.nominating_institution or 'N/A')
            raw_sheet.write(row, 7, reg.phone_number or 'N/A')
            raw_sheet.write(row, 8, reg.email or 'N/A')
            raw_sheet.write(row, 9, reg.submitted_at.strftime('%Y-%m-%d %H:%M:%S'))
            row += 1
            
        workbook.close()
        output.seek(0)
        
        response = HttpResponse(
            output.read(), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=Analytics_{pivot}.xlsx'
        return response

    @action(detail=False, methods=['get'], permission_classes=[], url_path='check_duplicate')
    def check_duplicate(self, request):
        """
        GET /api/v1/registrations/check_duplicate/?national_id=...&phone=...&email=...
        Public endpoint to check if a participant has already registered.
        """
        nat_id = (request.query_params.get('national_id') or '').strip()
        phone = (request.query_params.get('phone') or '').strip()
        # email check removed

        active_regs = Registration.objects.exclude(status=Registration.Status.REJECTED)

        nat_id_dup = bool(nat_id and active_regs.filter(national_id_number__iexact=nat_id).exists())

        return Response({
            'is_duplicate': nat_id_dup,
            'fields': {
                'national_id': nat_id_dup,
                'phone': False,
                'email': False,
            }
        })

    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser], url_path='download_pdf')
    def download_pdf(self, request, pk=None):
        """
        GET /api/v1/registrations/{id}/download_pdf/
        Generates and downloads the single candidate official dossier PDF.
        """
        reg = self.get_object()
        try:
            pdf_bytes = generate_registration_pdf(reg)
            safe_name = "".join([c for c in reg.full_name if c.isalnum() or c == ' ']).strip()
            filename = f"Candidate_{reg.id}_{safe_name.replace(' ', '_')}.pdf"
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            print(f"Error generating PDF for reg {reg.id}: {e}")
            return Response({'error': f'Failed to generate PDF: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

        zip_buffer = io.BytesIO()
        logo_data_uri = get_logo_data_uri()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for reg in registrations:
                try:
                    pdf_bytes = generate_registration_pdf(reg, logo_data_uri=logo_data_uri)
                    safe_name = "".join([c for c in reg.full_name if c.isalnum() or c == ' ']).strip()
                    filename = f"Candidate_{reg.id}_{safe_name.replace(' ', '_')}.pdf"
                    zip_file.writestr(filename, pdf_bytes)
                except Exception as e:
                    print(f"Error generating PDF for candidate {reg.id} in bulk download: {e}")

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
        from django.core.cache import cache
        data = cache.get('competition_info_public')
        if not data:
            settings = CompetitionSettings.load()
            serializer = CompetitionInfoSerializer(settings)
            data = serializer.data
            cache.set('competition_info_public', data, 60 * 60 * 12)  # Cache for 12 hours (invalidated on new registration)
        return Response(data)

    def put(self, request):
        """Full update — all fields must be supplied."""
        settings = CompetitionSettings.load()
        serializer = CompetitionInfoAdminSerializer(settings, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        from django.core.cache import cache
        cache.delete('competition_info_public')
        return Response(serializer.data)

    def patch(self, request):
        """Partial update — only the supplied fields are changed."""
        settings = CompetitionSettings.load()
        serializer = CompetitionInfoAdminSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        from django.core.cache import cache
        cache.delete('competition_info_public')
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/logs/ — list all audit logs
    GET /api/v1/logs/{id}/ — retrieve a specific audit log
    Admin only.
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['action', 'module', 'record_name', 'user']
