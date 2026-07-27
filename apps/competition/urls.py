"""
URL routing for the competition app using DRF routers.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, RegistrationViewSet, CompetitionInfoView

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'registrations', RegistrationViewSet, basename='registration')

urlpatterns = [
    path('', include(router.urls)),
    path('info/', CompetitionInfoView.as_view(), name='competition-info'),
]
