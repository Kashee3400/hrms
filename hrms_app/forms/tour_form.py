from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from ..models import UserTour
from bootstrap_datepicker_plus.widgets import (
    DatePickerInput,
    TimePickerInput,
)
from django.conf import settings

class BaseUserTourForm(forms.ModelForm):
    """Base form for tour applications with common functionality"""
    
    reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": _("Enter your reason or remarks"),
            }
        ),
        label=_("Reason/Remarks"),
        required=False,
        help_text=_("Optional: Add any additional comments")
    )
    
    class Meta:
        model = UserTour
        fields = []
        widgets = {
            "start_date": DatePickerInput(attrs={"class": "form-control"}),
            "start_time": TimePickerInput(
                options={"format": "hh:mm A", "showClear": True},
                attrs={"class": "form-control"},
            ),
            "end_date": DatePickerInput(attrs={"class": "form-control"}),
            "end_time": TimePickerInput(
                options={"format": "hh:mm A", "showClear": True},
                attrs={"class": "form-control"},
            ),
        }


class TourApplicationForm(BaseUserTourForm):
    """Form for creating/updating tour applications"""
    
    class Meta(BaseUserTourForm.Meta):
        fields = [
            "from_destination",
            "to_destination",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "remarks",
        ]
        widgets = {
            **BaseUserTourForm.Meta.widgets,
            "from_destination": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., Delhi")}
            ),
            "to_destination": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., Mumbai")}
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Purpose of tour"),
                }
            ),
        }
    
    def clean(self):
        """Validate tour dates"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        
        if start_date and end_date and end_date < start_date:
            raise ValidationError(
                _("End date must be after start date."),
                code="invalid_dates"
            )
        
        return cleaned_data


class EmployeeTourStatusUpdateForm(BaseUserTourForm):
    """Form for employees to manage their tour status"""
    
    status = forms.ChoiceField(
        choices=[
            ('extended', _('Request Extension')),
            ('pending_cancellation', _('Request Cancellation')),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Action"),
        help_text=_("Choose an action for your tour")
    )
    
    extended_end_date = forms.DateField(
        required=False,
        widget=DatePickerInput(attrs={"class": "form-control"}),
        label=_("New End Date"),
        help_text=_("Required when requesting extension")
    )
    
    extended_end_time = forms.TimeField(
        required=False,
        widget=TimePickerInput(
            options={"format": "hh:mm A", "showClear": True},
            attrs={"class": "form-control"},
        ),
        label=_("New End Time"),
        help_text=_("Required when requesting extension")
    )
    
    class Meta(BaseUserTourForm.Meta):
        fields = ["status", "extended_end_date", "extended_end_time"]
    
    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        self.instance = instance
    
    def clean(self):
        """Validate employee tour extension"""
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        extended_end_date = cleaned_data.get("extended_end_date")
        extended_end_time = cleaned_data.get("extended_end_time")
        
        # Validate extension fields
        if status == 'extended':
            if not extended_end_date or not extended_end_time:
                raise ValidationError(
                    _("New end date and time are required for extension."),
                    code="missing_extension_dates"
                )
            
            if self.instance and extended_end_date < self.instance.end_date:
                raise ValidationError(
                    _("New end date must be after the original end date."),
                    code="invalid_extended_date"
                )
        
        # Reason is required for cancellation
        if status == 'pending_cancellation' and not self.cleaned_data.get("reason"):
            raise ValidationError(
                _("Reason is required when requesting cancellation."),
                code="missing_reason"
            )
        
        return cleaned_data


class ManagerTourStatusUpdateForm(BaseUserTourForm):
    """Form for managers to approve/reject/cancel tours"""
    
    status = forms.ChoiceField(
        choices=[
            ('approved', _('Approve')),
            ('rejected', _('Reject')),
            ('cancelled', _('Cancel')),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Action"),
        help_text=_("Choose an action to manage the tour")
    )
    
    class Meta(BaseUserTourForm.Meta):
        fields = ["status"]
    
    def clean(self):
        """Validate manager actions"""
        cleaned_data = super().clean()
        reason = self.cleaned_data.get("reason")
        status = cleaned_data.get("status")
        
        # Reason is required for rejection
        if status == 'rejected' and not reason:
            raise ValidationError(
                _("Reason is required when rejecting a tour."),
                code="missing_rejection_reason"
            )
        
        return cleaned_data


class AdminTourStatusUpdateForm(BaseUserTourForm):
    """Form for admins with full control over tour status"""
    
    status = forms.ChoiceField(
        choices=settings.TOUR_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Tour Status"),
    )
    
    extended_end_date = forms.DateField(
        required=False,
        widget=DatePickerInput(attrs={"class": "form-control"}),
        label=_("Extended End Date"),
    )
    
    extended_end_time = forms.TimeField(
        required=False,
        widget=TimePickerInput(
            options={"format": "hh:mm A", "showClear": True},
            attrs={"class": "form-control"},
        ),
        label=_("Extended End Time"),
    )
    
    class Meta(BaseUserTourForm.Meta):
        fields = ["status", "extended_end_date", "extended_end_time"]
    
    def clean(self):
        """Validate admin tour changes"""
        cleaned_data = super().clean()
        extended_end_date = cleaned_data.get("extended_end_date")
        
        if extended_end_date and self.instance:
            if extended_end_date <= self.instance.end_date:
                raise ValidationError(
                    _("Extended end date must be after the original end date."),
                    code="invalid_extended_date"
                )
        
        return cleaned_data