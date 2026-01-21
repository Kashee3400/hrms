from django import forms
from hrms_app.models import LeaveApplication,LeaveType
from bootstrap_datepicker_plus.widgets import (
    DatePickerInput,
    TimePickerInput,
)
from hrms_app.utility.leave_utils import ShortLeavePolicyManager
from django_ckeditor_5.widgets import CKEditor5Widget

from django.utils.translation import gettext_lazy as _

class ShortLeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = [
            "leave_type",
            "startDate",
            "from_time",
            "leave_address",
            "to_time",
            "usedLeave",
            "balanceLeave",
            "reason",
        ]
        widgets = {
            "startDate": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "from_time": TimePickerInput(
                options={
                    "format": "hh:mm A",
                    "showClear": True,
                    "showClose": True,
                },
                
                attrs={"class": "form-control"},
            ),
            "to_time": TimePickerInput(
                options={
                    "format": "hh:mm A",
                    "showClear": True,
                    "showClose": True,
                },
                # range_from="from_time",
                attrs={"class": "form-control"},
            ),
            "usedLeave": forms.TextInput(
                attrs={"type": "text", "data-role": "input", "readonly": "readonly"}
            ),
            "leave_address": forms.TextInput(
                attrs={"type": "text", "class": "form-control"}
            ),
            "balanceLeave": forms.TextInput(
                attrs={"type": "text", "data-role": "input", "readonly": "readonly"}
            ),
            "reason": CKEditor5Widget(attrs={"class": "django_ckeditor_5"}),
        }
        labels = {
            "startDate": _("Date"),
            "from_time": _("From Time"),
            "to_time": _("To Time"),
            "usedLeave": _("Currently Booked"),
            "leave_address": _("Leave Address"),
            "balanceLeave": _("Available Balance"),
            "reason": _("Reason"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # 🔒 Force Short Leave type
        short_leave = LeaveType.objects.get(leave_type_short_code="STL")
        self.fields["leave_type"].initial = short_leave
        self.fields["leave_type"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("startDate")
        from_time = cleaned_data.get("from_time")
        to_time = cleaned_data.get("to_time")
        leaveTypeId = cleaned_data.get("leave_type")
        

        if not start_date:
            self.add_error("startDate", _("Date is required."))

        if not from_time:
            self.add_error("from_time", _("From Time is required."))

        if not to_time:
            self.add_error("to_time", _("To Time is required."))

        if from_time and to_time and from_time >= to_time:
            self.add_error("to_time", _("To Time must be after From Time."))

        if self.errors:
            return cleaned_data

        # 🔥 Policy Manager integration
        policy = ShortLeavePolicyManager(
            user=self.user,
            leave_type=leaveTypeId,
            start_date=start_date,
            from_time=from_time,
            to_time=to_time,
        )

        policy.apply()

        return cleaned_data
