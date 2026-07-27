from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CompetitionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.competition'
    verbose_name = _('Competition')
