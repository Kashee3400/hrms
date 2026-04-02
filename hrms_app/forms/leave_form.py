"""
forms.py  —  LeaveApplicationForm (Updated)

Changes from original
──────────────────────
1. SL attachment threshold fixed: > 3 → > 5 (policy says 5 consecutive days)
2. LeavePolicyManager kwarg renamed: bookedLeave= → booked_leave=
3. Policy validation now runs on BOTH create AND update
   (update uses exclude_application_id to skip self)
4. balanceLeave.initial now resolves period correctly via LeaveDomainService
   so EL (financial year) and monthly leaves get the right balance
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_ckeditor_5.widgets import CKEditor5Widget
from bootstrap_datepicker_plus.widgets import DatePickerInput

from ..models import LeaveType, LeaveApplication
from ..manager.leave_policy import LeavePolicyManager
from ..services.leave_service import LeaveDomainService


class LeaveApplicationForm(forms.ModelForm):

    class Meta:
        model = LeaveApplication
        fields = [
            "leave_type",
            "startDate",
            "endDate",
            "leave_address",
            "startDayChoice",
            "endDayChoice",
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
            "endDate": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                range_from="startDate",
                attrs={"class": "form-control"},
            ),
            "startDayChoice": forms.Select(
                attrs={"class": "leaveOption id_startDayChoice"}
            ),
            "endDayChoice": forms.Select(
                attrs={"class": "leaveOption id_endDayChoice"}
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
            "startDate":    _("Start Date"),
            "endDate":      _("End Date"),
            "usedLeave":    _("Currently Booked"),
            "leave_address":_("Leave Address"),
            "balanceLeave": _("Available Balance"),
            "reason":       _("Reason"),
            "startDayChoice": _("Start Day"),
            "endDayChoice":   _("End Day"),
        }

    # ─────────────────────────────────────────────────────────
    # INIT
    # ─────────────────────────────────────────────────────────

    def __init__(self, *args, **kwargs):
        self.user      = kwargs.pop("user", None)
        leave_type_id  = kwargs.pop("leave_type", None)
        super().__init__(*args, **kwargs)

        leave_type_obj = LeaveType.objects.filter(id=leave_type_id).first()

        # ── FIX 1: Resolve balance using period-aware LeaveDomainService ──
        # Previously used LeaveStatsManager directly with hardcoded year,
        # which gave wrong balance for EL (financial year) and monthly leaves.
        if leave_type_obj and self.user:
            today = timezone.now().date()
            remaining = LeaveDomainService.get_remaining_balance(
                user=self.user,
                leave_type=leave_type_obj,
                target_date=today,
            )
            self.fields["balanceLeave"].initial = remaining

        # ── SL attachment field ───────────────────────────────────────────
        if leave_type_obj and leave_type_obj.leave_type_short_code == "SL":
            self.fields["attachment"] = forms.FileField(
                required=False,
                label=_("Attachment"),
                help_text=_(
                    # FIX 2 (documented here): threshold is 5 consecutive days per policy,
                    # not 3. The clean() method enforces > 5.
                    "Upload a medical certificate or supporting document "
                    "(required for Sick Leave exceeding 5 consecutive days)."
                ),
                widget=forms.ClearableFileInput(
                    attrs={
                        "class": "form-control-file",
                        "accept": ".pdf,.jpg,.jpeg,.png",
                    }
                ),
            )

        self.fields["leave_type"].initial = leave_type_id

    # ─────────────────────────────────────────────────────────
    # CLEAN
    # ─────────────────────────────────────────────────────────

    def clean(self):
        cleaned_data    = super().clean()
        startDate       = cleaned_data.get("startDate")
        endDate         = cleaned_data.get("endDate")
        usedLeave       = cleaned_data.get("usedLeave")
        leaveTypeId     = cleaned_data.get("leave_type")
        startDayChoice  = cleaned_data.get("startDayChoice")
        endDayChoice    = cleaned_data.get("endDayChoice")
        attachment      = cleaned_data.get("attachment")
        leave_address   = cleaned_data.get("leave_address")
        reason          = cleaned_data.get("reason")

        # ── Basic presence checks ─────────────────────────────────────────
        if not startDate:
            self.add_error("startDate", _("Start Date is required."))
        if not endDate:
            self.add_error("endDate", _("End Date is required."))
        if not startDate or not endDate:
            return cleaned_data

        if startDate > endDate:
            self.add_error("endDate", _("End Date must be after Start Date."))
            return cleaned_data

        if not leave_address:
            self.add_error("leave_address", _("Leave Address is required."))
        if not reason:
            self.add_error("reason", _("Reason is required."))

        # ── FIX 2: SL attachment threshold corrected from >3 to >5 ───────
        # HR policy: medical certificate required only if SL exceeds
        # 5 *consecutive* days (not 3 as previously coded).
        if (
            leaveTypeId
            and leaveTypeId.leave_type_short_code == "SL"
            and usedLeave
            and float(usedLeave) > 5          # ← was: int(usedLeave) > 3
        ):
            if not attachment:
                self.add_error(
                    "attachment",
                    _(
                        "A medical certificate is required for Sick Leave "
                        "applications exceeding 5 consecutive days."
                    ),
                )

        # ── FIX 3 + FIX 4: Policy validation runs on BOTH create AND edit ─
        # Previously skipped on edit (update). Now always runs.
        # exclude_application_id ensures the current application is not
        # counted as an "overlap" with itself during update.
        exclude_application_id = (
            self.instance.pk if self.instance and self.instance.pk else None
        )

        try:
            policy_manager = LeavePolicyManager(
                user=self.user,
                leave_type=leaveTypeId,
                start_date=startDate,
                end_date=endDate,
                start_day_choice=startDayChoice,
                end_day_choice=endDayChoice,
                booked_leave=usedLeave,          # ← FIX 3: was bookedLeave=
                exclude_application_id=exclude_application_id,
            )
            policy_manager.validate_policies()
        except ValidationError as e:
            self.add_error(None, str(e))

        return cleaned_data