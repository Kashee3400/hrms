"""
forms.py — LeavePolicyConfig Form
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from ..models import LeaveType
from ..models_leave_policy_config import LeavePolicyConfig


class LeavePolicyConfigForm(forms.ModelForm):

    class Meta:
        model  = LeavePolicyConfig
        exclude = ["leave_type", "created_by", "updated_by", "created_at", "updated_at"]

        widgets = {
            # ── Dates ─────────────────────────────────────────────
            "effective_from": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
            "effective_to": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),

            # ── Numbers ───────────────────────────────────────────
            "annual_entitlement":                     forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "min_notice_days":                        forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "max_consecutive_days":                   forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "min_days_per_application":               forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "max_spells_per_year":                    forms.NumberInput(attrs={"class": "form-control"}),
            "retrospective_application_working_days": forms.NumberInput(attrs={"class": "form-control"}),
            "max_carry_forward_days":                 forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "max_accumulation_days":                  forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "encashment_max_times_per_year":          forms.NumberInput(attrs={"class": "form-control"}),
            "encashment_min_days":                    forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "encashment_min_balance_after":           forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "max_advance_leave_days":                 forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "max_short_leaves_per_month":             forms.NumberInput(attrs={"class": "form-control"}),
            "max_short_leave_hours_per_occasion":     forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "paternity_days_before_birth":            forms.NumberInput(attrs={"class": "form-control"}),
            "paternity_days_after_birth":             forms.NumberInput(attrs={"class": "form-control"}),
            "paternity_max_times_in_tenure":          forms.NumberInput(attrs={"class": "form-control"}),

            # ── Selects ───────────────────────────────────────────
            "accrual_period":     forms.Select(attrs={"class": "form-control select2"}),
            "calculation_period": forms.Select(attrs={"class": "form-control select2"}),

            # ── M2M ───────────────────────────────────────────────
            "can_club_with": forms.SelectMultiple(attrs={"class": "form-control select2", "multiple": "multiple"}),
        }

        labels = {
            "effective_from":                         _("Effective From"),
            "effective_to":                           _("Effective To (leave blank = currently active)"),
            "annual_entitlement":                     _("Annual Entitlement (Days)"),
            "accrual_period":                         _("Accrual Period"),
            "calculation_period":                     _("Calculation Period"),
            "min_notice_days":                        _("Min Notice Days"),
            "max_consecutive_days":                   _("Max Consecutive Days"),
            "min_days_per_application":               _("Min Days Per Application"),
            "max_spells_per_year":                    _("Max Spells Per Year"),
            "allow_half_day":                         _("Allow Half Day"),
            "half_day_only_as_prefix_suffix":         _("Half Day Only as Prefix / Suffix (EL rule)"),
            "retrospective_application_working_days": _("Retrospective Application Window (Working Days)"),
            "requires_confirmation":                  _("Requires Confirmation (Post-Probation)"),
            "cannot_combine_with_any":                _("Cannot Combine With Any Other Leave"),
            "can_club_with":                          _("Can Club With (specific types)"),
            "allow_carry_forward":                    _("Allow Carry Forward"),
            "max_carry_forward_days":                 _("Max Carry Forward Days"),
            "max_accumulation_days":                  _("Max Accumulation Days"),
            "lapse_unused_at_period_end":             _("Lapse Unused at Period End"),
            "is_encashable":                          _("Is Encashable"),
            "encashment_max_times_per_year":          _("Max Encashments Per Year"),
            "encashment_min_days":                    _("Min Days Per Encashment"),
            "encashment_min_balance_after":           _("Min Balance Must Remain After Encashment"),
            "encashable_on_separation":               _("Encashable on Separation"),
            "no_encashment_on_misconduct":            _("Block Encashment on Misconduct Termination"),
            "allow_advance_leave":                    _("Allow Advance Leave"),
            "max_advance_leave_days":                 _("Max Advance Leave Days"),
            "max_short_leaves_per_month":             _("Max Short Leaves Per Month"),
            "max_short_leave_hours_per_occasion":     _("Max Hours Per Short Leave Occasion"),
            "paternity_days_before_birth":            _("Days Before Birth (Paternity Window)"),
            "paternity_days_after_birth":             _("Days After Birth (Paternity Window)"),
            "paternity_max_times_in_tenure":          _("Max Times in Tenure (Paternity)"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # effective_to is optional
        self.fields["effective_to"].required = False

        # Exclude current leave type from can_club_with if editing
        if self.instance and self.instance.pk and self.instance.leave_type_id:
            self.fields["can_club_with"].queryset = LeaveType.objects.exclude(
                pk=self.instance.leave_type_id
            )

        # Mark all optional fields
        optional_fields = [
            "effective_to", "max_consecutive_days", "min_days_per_application",
            "max_spells_per_year", "max_carry_forward_days", "max_accumulation_days",
            "encashment_max_times_per_year", "encashment_min_days",
            "encashment_min_balance_after", "max_advance_leave_days",
            "max_short_leaves_per_month", "max_short_leave_hours_per_occasion",
            "paternity_days_before_birth", "paternity_days_after_birth",
            "paternity_max_times_in_tenure", "can_club_with", "encashment_triggers",
        ]
        for f in optional_fields:
            if f in self.fields:
                self.fields[f].required = False

    def clean(self):
        cleaned = super().clean()
        eff_from = cleaned.get("effective_from")
        eff_to   = cleaned.get("effective_to")

        if eff_from and eff_to and eff_to <= eff_from:
            self.add_error("effective_to", _("Effective To must be after Effective From."))

        allow_cf  = cleaned.get("allow_carry_forward")
        max_cf    = cleaned.get("max_carry_forward_days")
        if not allow_cf and max_cf:
            self.add_error(
                "max_carry_forward_days",
                _("Max Carry Forward Days is only relevant when Allow Carry Forward is enabled.")
            )

        is_enc       = cleaned.get("is_encashable")
        enc_max      = cleaned.get("encashment_max_times_per_year")
        enc_min      = cleaned.get("encashment_min_days")
        if not is_enc and (enc_max or enc_min):
            self.add_error(
                "encashment_max_times_per_year",
                _("Encashment fields are only relevant when Is Encashable is enabled.")
            )

        return cleaned