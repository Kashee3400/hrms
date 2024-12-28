from import_export import resources,fields
from hrms_app.models import CustomUser,Holiday,UserTour

class CustomUserResource(resources.ModelResource):
    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'first_name', 'last_name', 'official_email', 
            'is_superuser', 'is_staff', 'is_active', 'date_joined', 'last_login',
            'is_rm', 'reports_to', 'role', 'device_location'
        )  # Specify fields to include in import/export
        export_order = fields  # Ensure consistent column order in exports

class HolidayResource(resources.ModelResource):
    class Meta:
        model = Holiday
        fields = ('id', 'title', 'short_code', 'start_date', 'end_date', 'desc', 'color_hex')
        export_order = ('id', 'title', 'short_code', 'start_date', 'end_date', 'desc', 'color_hex')
        
class UserTourResource(resources.ModelResource):
    applied_by_full_name = fields.Field()
    class Meta:
        model = UserTour
        fields = ('approval_type', 'applied_by__username','applied_by_full_name', 'from_destination', 'to_destination', 'start_date','start_time', 'end_date','end_time','extended_end_date','extended_end_time', 'status', 'total','bills_submitted')
        
    def dehydrate_applied_by_full_name(self, obj):
        """
        Define the logic for populating the custom field.
        This method is called during export.
        """
        if obj.applied_by:
            return f"{obj.applied_by.get_full_name()}"
        return "Unknown"  # Default value if no user is associated

