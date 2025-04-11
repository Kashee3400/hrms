from import_export import resources, fields
from hrms_app.models import CustomUser, Holiday, UserTour, LeaveTransaction,PermanentAddress,PersonalDetails
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserResource(resources.ModelResource):
    class Meta:
        model = CustomUser
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "official_email",
            "is_superuser",
            "is_staff",
            "is_active",
            "date_joined",
            "last_login",
            "is_rm",
            "reports_to",
            "role",
            "device_location",
        ) 
        export_order = fields  # Ensure consistent column order in exports



class PersonalDetailsResource(resources.ModelResource):
    user = fields.Field(
        column_name='user',
        attribute='user',
        widget=ForeignKeyWidget(User, 'username')  # Adjust to 'email' or 'id' if needed
    )
    gender = fields.Field(
        column_name='gender',
        attribute='gender',
        widget=ForeignKeyWidget(PersonalDetails._meta.get_field('gender').remote_field.model, 'gender')  # Replace 'name' with actual identifier
    )
    designation = fields.Field(
        column_name='designation',
        attribute='designation',
        widget=ForeignKeyWidget(PersonalDetails._meta.get_field('designation').remote_field.model, 'designation')  # Replace 'name'
    )
    religion = fields.Field(
        column_name='religion',
        attribute='religion',
        widget=ForeignKeyWidget(PersonalDetails._meta.get_field('religion').remote_field.model, 'religion'),  # Replace 'name'
    )
    marital_status = fields.Field(
        column_name='marital_status',
        attribute='marital_status',
        widget=ForeignKeyWidget(PersonalDetails._meta.get_field('marital_status').remote_field.model, 'marital_status'),  # Replace 'name'
    )

    class Meta:
        model = PersonalDetails
        fields = (
            'id',
            'salutation',
            'employee_code',
            'user',
            'mobile_number',
            'alt_mobile_number',
            'cug_mobile_number',
            'gender',
            'designation',
            'official_mobile_number',
            'religion',
            'marital_status',
            'birthday',
            'marriage_ann',
            'doj',
            'dol',
            'dor',
            'dot',
            'dof',
        )
        export_order = fields  # Optional: to maintain consistent column order



class HolidayResource(resources.ModelResource):
    class Meta:
        model = Holiday
        fields = (
            "id",
            "title",
            "short_code",
            "start_date",
            "end_date",
            "desc",
            "color_hex",
        )
        export_order = (
            "id",
            "title",
            "short_code",
            "start_date",
            "end_date",
            "desc",
            "color_hex",
        )


class UserTourResource(resources.ModelResource):
    applied_by_full_name = fields.Field()

    class Meta:
        model = UserTour
        fields = (
            "approval_type",
            "applied_by__username",
            "applied_by_full_name",
            "from_destination",
            "to_destination",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "extended_end_date",
            "extended_end_time",
            "status",
            "total",
            "bills_submitted",
        )

    def dehydrate_applied_by_full_name(self, obj):
        """
        Define the logic for populating the custom field.
        This method is called during export.
        """
        if obj.applied_by:
            return f"{obj.applied_by.get_full_name()}"
        return "Unknown"  # Default value if no user is associated


class LeaveTransactionResource(resources.ModelResource):
    class Meta:
        model = LeaveTransaction
        fields = (
            "id",
            "leave_balance__user__username",
            "leave_balance__user__first_name",
            "leave_balance__user__last_name",
            "leave_type__leave_type",
            "transaction_date",
            "no_of_days_applied",
            "no_of_days_approved",
            "transaction_type",
            "remarks",
        )
        export_order = fields
