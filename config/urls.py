"""
URL Configuration for the Quran Competition Portal API.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.utils.translation import gettext_lazy as _

admin.site.site_header = _('Quran Competition Admin')
admin.site.site_title = _('Quran Competition')
admin.site.index_title = _('Administration Portal')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.competition.urls')),
    path('api/v1/auth/', include('apps.accounts.urls')),
    # i18n URL patterns for Django admin language switching
    path('i18n/', include('django.conf.urls.i18n')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
