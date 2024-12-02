from import_export import resources
from hrms_app.models import CustomUser

class CustomUserResource(resources.ModelResource):
    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'first_name', 'last_name', 'official_email', 
            'is_superuser', 'is_staff', 'is_active', 'date_joined', 'last_login',
            'is_rm', 'reports_to', 'role', 'device_location'
        )  # Specify fields to include in import/export
        export_order = fields  # Ensure consistent column order in exports

