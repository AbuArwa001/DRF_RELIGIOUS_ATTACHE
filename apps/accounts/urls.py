"""
URL routing for JWT auth endpoints.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
