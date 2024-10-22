from django.apps import AppConfig


class HrmsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hrms_app'
    
    def ready(self):
        import hrms_app.signals
