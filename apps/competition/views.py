"""
DRF ViewSets for the competition app.
"""
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Registration, CompetitionSettings
from .serializers import (
    CategorySerializer,
    CompetitionInfoSerializer,
    RegistrationCreateSerializer,
    RegistrationAdminSerializer,
)
from .permissions import IsAdminUser


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
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST   /api/v1/registrations/       — public: submit a registration (multipart)
    GET    /api/v1/registrations/       — admin only: list all registrations
    GET    /api/v1/registrations/{id}/  — admin only: retrieve one registration
    PUT    /api/v1/registrations/{id}/  — admin only: full update (status, notes)
    PATCH  /api/v1/registrations/{id}/  — admin only: partial update
    """
    queryset = Registration.objects.select_related('category').all()

    def get_serializer_class(self):
        if self.action == 'create':
            return RegistrationCreateSerializer
        return RegistrationAdminSerializer

    def get_permissions(self):
        if self.action == 'create':
            return []   # public registration submission
        return [IsAdminUser()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            RegistrationCreateSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def review(self, request, pk=None):
        """
        PATCH /api/v1/registrations/{id}/review/
        Allows updating status and reviewer_notes only.
        """
        registration = self.get_object()
        allowed_fields = {'status', 'reviewer_notes'}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        serializer = RegistrationAdminSerializer(registration, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CompetitionInfoView(APIView):
    """
    GET /api/v1/info/
    Returns competition settings (dates, venue, about text).
    Public endpoint.
    """
    permission_classes = []

    def get(self, request):
        settings = CompetitionSettings.load()
        serializer = CompetitionInfoSerializer(settings)
        return Response(serializer.data)
