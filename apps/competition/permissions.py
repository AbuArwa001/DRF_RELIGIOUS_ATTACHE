"""
Custom DRF permissions for the competition app.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """
    Allows read-only access for everyone.
    Write access is restricted to authenticated admin users.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsAdminUser(BasePermission):
    """Allow access only to staff/admin users."""
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
