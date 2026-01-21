# admin_forms.py
from django import forms
from ..models import LeaveType


class LeaveTypeAdminForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = [
            "leave_type",
            "leave_type_short_code",
            "half_day_short_code",
            "leave_unit",
            "allow_half_day",
            "half_day_value",
            "min_duration",
            "max_duration",
            "accrual_period",
            "accrual_quantity",
            "expiry_policy",
            "must_apply_within_accrual_period",
            "allow_carry_forward",
            "max_carry_forward",
            "default_allocation",
            "allowed_days_per_year",
            "min_days_limit",
            "max_days_limit",
            "min_notice_days",
            "leave_fy_start",
            "leave_fy_end",
            "color_hex",
            "text_color_hex",
            "consecutive_restriction",
            "restricted_after_leave_types",
        ]

    class Media:
        js = ("admin/js/leave_type_admin.js",)
        css = {
            "all": ("admin/css/leave_type_admin.css",)
        }
