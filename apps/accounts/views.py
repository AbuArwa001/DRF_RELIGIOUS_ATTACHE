"""
JWT authentication views for the accounts app.
Wraps simplejwt token views with locale-aware error responses.
"""
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Add the username and staff flag to the token response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        data['is_staff'] = self.user.is_staff
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
