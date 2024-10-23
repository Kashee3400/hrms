from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from hrms_app.hrms.form import *
from .models import *
from django_ckeditor_5.widgets import CKEditor5Widget

admin.site.site_title = "HRMS"
admin.site.site_header = "HRMS Administration"


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'first_name', 'last_name', 'official_email', 'is_superuser', 'is_staff', 'is_active',
                    'date_joined', 'last_login']
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('official_email', 'is_rm', 'reports_to','role','device_location')}),
    )
    # add_fieldsets = UserAdmin.add_fieldsets + (
    #     (None, {'fields': ('role',)}),
    # )


admin.site.register(CustomUser, CustomUserAdmin)

from django.utils.safestring import mark_safe


class LeaveTypeAdmin(admin.ModelAdmin):
    form = LeaveTypeForm
    list_display = ['leave_type', 'leave_type_short_code', 'min_notice_days'
        , 'max_days_limit', 'min_days_limit', 'allowed_days_per_year', 'leave_fy_start', 'leave_fy_end',
                    'color_representation', 'text_color_representation', 'created_at', 'created_by', 'updated_at',
                    'updated_by','consecutive_restriction']
    
    search_fields = ['leave_type']
    
    filter_horizontal = ['restricted_after_leave_types']

    def color_representation(self, obj):
        return mark_safe(f'<div style="width: 30px; height: 20px; background-color: {obj.color_hex}"></div>')

    color_representation.short_description = 'Color'

    def save_model(self, request, obj, form, change):
        obj._current_user = request.user
        super().save_model(request, obj, form, change)

    def text_color_representation(self, obj):
        return mark_safe(f'<div style="width: 30px; height: 20px; background-color: {obj.text_color_hex}"></div>')

    text_color_representation.short_description = 'Text Color'


admin.site.register(LeaveType, LeaveTypeAdmin)


class HolidayAdmin(admin.ModelAdmin):
    form = HolidayForm

    list_display = ['title', 'short_code', 'start_date'
        , 'end_date', 'desc', 'color_representation']

    def color_representation(self, obj):
        return mark_safe(f'<div style="width: 30px; height: 20px; background-color: {obj.color_hex}"></div>')

    color_representation.short_description = 'Color'


admin.site.register(Holiday, HolidayAdmin)


class AttendanceStatusColorAdmin(admin.ModelAdmin):
    form = AttendanceStatusColorForm

    list_display = ['status', 'color', 'color_representation', 'created_at']

    def color_representation(self, obj):
        return mark_safe(f'<div style="width: 30px; height: 20px; background-color: {obj.color_hex}"></div>')

    color_representation.short_description = 'Color'


admin.site.register(AttendanceStatusColor, AttendanceStatusColorAdmin)


class AttendanceSettingAdmin(admin.ModelAdmin):
    list_display = ['full_day_hours', 'half_day_hours', 'created_at', 'updated_at']


admin.site.register(AttendanceSetting, AttendanceSettingAdmin)


class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = (
        'applied_by', 'start_date', 'end_date', 'att_status', 'duration', 'color_representation', 'is_regularisation',
        'is_submitted')
    search_fields = ['applied_by__first_name', 'applied_by__last_name']

    def color_representation(self, obj):
        return mark_safe(f'<div style="width: 30px; height: 20px; background-color: {obj.color_hex}"></div>')

    color_representation.short_description = 'Status Color'


admin.site.register(AttendanceLog, AttendanceLogAdmin)


class AttendanceLogActionAdmin(admin.ModelAdmin):
    list_display = ('log', 'action_by', 'action_by_name', 'action_by_email', 'action', 'timestamp', 'notes')
    search_fields = ['action_by__first_name', 'action_by__last_name', 'action_by_email']


admin.site.register(AttendanceLogAction, AttendanceLogActionAdmin)


class UserTourAdmin(admin.ModelAdmin):
    list_display = ('applied_by', 'from_destination', 'to_destination', 'start_date', 'end_date', 'status')
    formfield_overrides = {
        models.TextField: {'widget': CKEditor5Widget()},
    }


admin.site.register(UserTour, UserTourAdmin)


class LeaveBalanceOpeningAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'leave_type', 'year', 'no_of_leaves', 'remaining_leave_balances', 'opening_balance','closing_balance','created_at', 'created_by',
        'updated_at',
        'updated_by')
    search_fields = ['user__first_name', 'user__last_name']
    
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


admin.site.register(LeaveBalanceOpenings, LeaveBalanceOpeningAdmin)


class PersonalDetailAdmin(admin.ModelAdmin):
    list_display = (
        'employee_code',
        'user',
        'avatar',
        'mobile_number',
        'alt_mobile_number',
        'gender',
        'designation',
        'official_mobile_number',
        'religion',
        'marital_status',
        'birthday',
        'ctc',
        'ann_date',
        'doj',
        'dol'
    )

    search_fields = ['user__first_name', 'user__last_name', 'employee_code', 'mobile_number', 'official_mobile_number']


admin.site.register(PersonalDetails, PersonalDetailAdmin)


class EmployeeShiftAdmin(admin.ModelAdmin):
    list_display = ['employee', 'shift_timing', 'created_at', 'created_by']
    search_fields = ['employee__first_name', 'employee__last_name']


admin.site.register(EmployeeShift, EmployeeShiftAdmin)


class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display = ['appliedBy', 'leave_type', 'applicationNo', 'applyingDate'
        , 'startDate', 'endDate', 'usedLeave', 'balanceLeave', 'status'
        , 'startDayChoice', 'endDayChoice', 'updatedAt']

    search_fields = ['leave_type__leave_type', 'appliedBy__first_name', 'appliedBy__last_name']


admin.site.register(LeaveApplication, LeaveApplicationAdmin)


class FormProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'step', 'status']

    search_fields = ['user__first_name', 'user__last_name', 'email']


admin.site.register(FormProgress, FormProgressAdmin)


class DeviceInformationAdmin(admin.ModelAdmin):
    list_display = ['device_location','from_date', 'to_date', 'serial_number','username','password']
    fields = ('device_location','api_link','from_date', 'to_date', 'serial_number','username','password')
    search_fields = ['serial_number', 'username']
    

admin.site.register(DeviceInformation, DeviceInformationAdmin)


class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ['location_name','office_type', 'address', 'latitude','longitude']
    fields = ('location_name','office_type', 'address', 'latitude','longitude')
    search_fields = ['location_name']
    filter = ['office_type']
    

admin.site.register(OfficeLocation, OfficeLocationAdmin)

class ShiftTimingAdmin(admin.ModelAdmin):
    list_display = ['start_time','end_time', 'grace_time', 'grace_start_time','grace_end_time','break_start_time','break_end_time','break_duration','is_active','role']
    fields = ['start_time','end_time', 'grace_time', 'grace_start_time','grace_end_time','break_start_time','break_end_time','break_duration','is_active','role']
    

admin.site.register(ShiftTiming, ShiftTimingAdmin)


class RoleAdmin(admin.ModelAdmin):
    list_display = ['name','description']    

admin.site.register(Role, RoleAdmin)



class NotificationAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'notification_type', 'is_read', 'timestamp')  # Fields to display in the list view
    list_filter = ('notification_type', 'is_read', 'timestamp')  # Fields to filter by
    search_fields = ('message',)  # Fields to search by
    ordering = ('-timestamp',)  # Default ordering

    fieldsets = (
        (None, {
            'fields': ('sender', 'receiver', 'message', 'notification_type', 'target_url', 'go_route_mobile', 'is_read')
        }),
        ('Related Object Info', {
            'fields': ('related_object_id', 'related_content_type')
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',),  # Optional: Collapse this section by default
        }),
    )

admin.site.register(Notification, NotificationAdmin)


@admin.register(LeaveDayChoiceAdjustment)
class LeaveDayChoiceAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('start_day_choice', 'end_day_choice', 'adjustment_value')
    list_filter = ('start_day_choice', 'end_day_choice')
    search_fields = ('start_day_choice', 'end_day_choice')



@admin.register(Logo)
class LogoAdmin(admin.ModelAdmin):
    list_display = ('logo', 'logo_image')
    search_fields = ('logo',)
    readonly_fields = ('logo_image',)  # Making logo_image read-only

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('department', 'is_active', 'created_at', 'updated_at')
    search_fields = ('department',)
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('designation', 'department', 'is_active', 'created_at', 'updated_at')
    search_fields = ('designation', 'department__department')
    list_filter = ('is_active', 'department')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

@admin.register(Gender)
class GenderAdmin(admin.ModelAdmin):
    list_display = ('gender', 'is_active', 'created_at')
    search_fields = ('gender',)
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_by', 'created_by')

@admin.register(MaritalStatus)
class MaritalStatusAdmin(admin.ModelAdmin):
    list_display = ('marital_status', 'is_active', 'created_at')
    search_fields = ('marital_status',)
    list_filter = ('is_active',)
    readonly_fields = ('created_at',)

