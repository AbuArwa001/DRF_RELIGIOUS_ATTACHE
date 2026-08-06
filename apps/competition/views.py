"""
DRF ViewSets for the competition app.
"""
from rest_framework import viewsets, mixins, status
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
    GET    /api/v1/registrations/              — admin: list all
    GET    /api/v1/registrations/{id}/         — admin: retrieve one
    PUT    /api/v1/registrations/{id}/         — admin: full update
    PATCH  /api/v1/registrations/{id}/         — admin: partial update
    DELETE /api/v1/registrations/{id}/         — admin: delete entry
    PATCH  /api/v1/registrations/{id}/review/  — admin: update status + notes
    GET    /api/v1/registrations/{id}/photo_url/ — admin: get presigned S3 URL for passport photo
    GET    /api/v1/registrations/{id}/doc_url/   — admin: get presigned S3 URL for ID document
    """
    queryset = Registration.objects.select_related('category').all()

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
        old_notes = instance.reviewer_notes
        serializer = RegistrationAdminSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        if updated_instance.status in ['rejected', 'approved'] and (old_status != updated_instance.status or old_notes != updated_instance.reviewer_notes):
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
        old_notes = registration.reviewer_notes
        allowed_fields = {'status', 'reviewer_notes'}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        serializer = RegistrationAdminSerializer(registration, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        if updated_instance.status in ['rejected', 'approved'] and (old_status != updated_instance.status or old_notes != updated_instance.reviewer_notes):
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
