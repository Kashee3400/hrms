from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class HrmsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hrms_app'
    label = 'hrms_app'
    icon = 'mdi-security'
    verbose_name = _('HR Admin')

    def ready(self):
        import hrms_app.signals
