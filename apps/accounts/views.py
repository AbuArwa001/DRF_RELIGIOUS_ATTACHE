"""
JWT authentication views for the accounts app.
Wraps simplejwt token views with locale-aware error responses.
"""
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from apps.competition.models import AuditLog


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Add the username and staff flag to the token response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        data['is_staff'] = self.user.is_staff
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            AuditLog.objects.create(
                user=request.data.get('username'),
                action='LOGIN',
                module='Auth',
                record_name=request.data.get('username'),
                ip_address=request.META.get('REMOTE_ADDR'),
                details={"message": "Admin successfully logged in"}
            )
        return response
