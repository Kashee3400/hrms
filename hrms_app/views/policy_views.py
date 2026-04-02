"""
views.py — Leave Policy Configuration Management
─────────────────────────────────────────────────
Provides:
  1. LeavePolicyConfigListView   — lists all leave types + their active policy
  2. LeavePolicyConfigCreateView — create a new policy version for a leave type
  3. LeavePolicyConfigUpdateView — edit the currently active policy
  4. LeavePolicyConfigHistoryView — AJAX: version history for a leave type
  5. LeavePolicyConfigCompareView — AJAX: side-by-side diff of two versions
"""

import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from ..models import LeaveType
from ..models_leave_policy_config import LeavePolicyConfig
from ..forms.policy_form import LeavePolicyConfigForm          # defined below in forms.py


# ─────────────────────────────────────────────────────────────────
# MIXIN — HR / Admin only
# ─────────────────────────────────────────────────────────────────

class HRAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow only staff / HR role users."""

    def test_func(self):
        user = self.request.user
        # Adjust this condition to match your role/permission setup
        return user.is_staff or getattr(user, "is_hr", False)

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to access this page.")
        return redirect("dashboard")  # adjust to your dashboard URL name


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

POLICY_FIELDS_LABELS = [
    # (field_name, display_label, group)
    ("annual_entitlement",                     "Annual Entitlement (Days)",              "Entitlement"),
    ("accrual_period",                         "Accrual Period",                         "Entitlement"),
    ("calculation_period",                     "Calculation Period",                     "Entitlement"),
    ("min_notice_days",                        "Min Notice Days",                        "Application Rules"),
    ("max_consecutive_days",                   "Max Consecutive Days",                   "Application Rules"),
    ("min_days_per_application",               "Min Days Per Application",               "Application Rules"),
    ("max_spells_per_year",                    "Max Spells Per Year",                    "Application Rules"),
    ("allow_half_day",                         "Allow Half Day",                         "Application Rules"),
    ("half_day_only_as_prefix_suffix",         "Half Day Only as Prefix/Suffix",         "Application Rules"),
    ("retrospective_application_working_days", "Retrospective Window (Working Days)",    "Application Rules"),
    ("requires_confirmation",                  "Requires Confirmation",                  "Eligibility"),
    ("cannot_combine_with_any",                "Cannot Combine With Any Leave",          "Eligibility"),
    ("allow_carry_forward",                    "Allow Carry Forward",                    "Carry Forward"),
    ("max_carry_forward_days",                 "Max Carry Forward Days",                 "Carry Forward"),
    ("max_accumulation_days",                  "Max Accumulation Days",                  "Carry Forward"),
    ("lapse_unused_at_period_end",             "Lapse Unused at Period End",             "Carry Forward"),
    ("is_encashable",                          "Is Encashable",                          "Encashment"),
    ("encashment_max_times_per_year",          "Max Encashments Per Year",               "Encashment"),
    ("encashment_min_days",                    "Min Days Per Encashment",                "Encashment"),
    ("encashment_min_balance_after",           "Min Balance After Encashment",           "Encashment"),
    ("encashable_on_separation",               "Encashable on Separation",               "Encashment"),
    ("no_encashment_on_misconduct",            "No Encashment on Misconduct",            "Encashment"),
    ("allow_advance_leave",                    "Allow Advance Leave",                    "Advanced"),
    ("max_advance_leave_days",                 "Max Advance Leave Days",                 "Advanced"),
    ("max_short_leaves_per_month",             "Max Short Leaves Per Month",             "Short Leave"),
    ("max_short_leave_hours_per_occasion",     "Max Hours Per Occasion",                 "Short Leave"),
    ("paternity_days_before_birth",            "Days Before Birth",                      "Paternity"),
    ("paternity_days_after_birth",             "Days After Birth",                       "Paternity"),
    ("paternity_max_times_in_tenure",          "Max Times in Tenure",                    "Paternity"),
]


def _policy_to_dict(config):
    """Serialize a LeavePolicyConfig instance to a flat dict for JSON/compare."""
    if config is None:
        return {}
    result = {}
    for field, label, group in POLICY_FIELDS_LABELS:
        val = getattr(config, field, None)
        result[field] = {
            "label": label,
            "group": group,
            "value": val,
        }
    return result


# ─────────────────────────────────────────────────────────────────
# 1. LIST VIEW
# ─────────────────────────────────────────────────────────────────

class LeavePolicyConfigListView(HRAdminRequiredMixin, View):
    template_name = "leave/policy_config/list.html"

    def get(self, request):
        leave_types = LeaveType.objects.prefetch_related("policy_versions").all()

        rows = []
        for lt in leave_types:
            active = LeavePolicyConfig.get_active_policy(lt, date.today())
            version_count = lt.policy_versions.count()
            rows.append({
                "leave_type":     lt,
                "active_policy":  active,
                "version_count":  version_count,
                "has_policy":     active is not None,
            })

        return render(request, self.template_name, {
            "rows":       rows,
            "page_title": "Leave Policy Configuration",
            "breadcrumb": [
                {"label": "HR",                    "url": ""},
                {"label": "Leave Policy Config",   "url": ""},
            ],
        })


# ─────────────────────────────────────────────────────────────────
# 2. CREATE VIEW
# ─────────────────────────────────────────────────────────────────

class LeavePolicyConfigCreateView(HRAdminRequiredMixin, View):
    template_name = "leave/policy_config/form.html"

    def get(self, request, leave_type_id):
        lt      = get_object_or_404(LeaveType, pk=leave_type_id)
        active  = LeavePolicyConfig.get_active_policy(lt, date.today())
        form    = LeavePolicyConfigForm(initial=self._get_initial(active))
        return render(request, self.template_name, self._ctx(lt, form, active, "Create"))

    def post(self, request, leave_type_id):
        lt     = get_object_or_404(LeaveType, pk=leave_type_id)
        active = LeavePolicyConfig.get_active_policy(lt, date.today())
        form   = LeavePolicyConfigForm(request.POST)

        if form.is_valid():
            new_effective_from = form.cleaned_data["effective_from"]

            # Close current active policy the day before the new one starts
            if active and active.effective_to is None:
                LeavePolicyConfig.close_current_policy(lt, new_effective_from)

            config              = form.save(commit=False)
            config.leave_type   = lt
            config.effective_to = None   # new version is open-ended (active)
            config.created_by   = request.user
            config.updated_by   = request.user

            try:
                config.full_clean()
                config.save()
                # Save M2M after save
                form.save_m2m()
                messages.success(
                    request,
                    f"New policy version for '{lt}' created successfully "
                    f"(effective from {new_effective_from})."
                )
                return redirect("leave:policy_config_list")
            except ValidationError as e:
                form.add_error(None, e)

        return render(request, self.template_name, self._ctx(lt, form, active, "Create"))

    def _get_initial(self, active):
        if not active:
            return {"effective_from": date.today()}
        d = {}
        for field, _, _ in POLICY_FIELDS_LABELS:
            d[field] = getattr(active, field, None)
        d["effective_from"] = date.today()
        return d

    def _ctx(self, lt, form, active, action):
        return {
            "leave_type":   lt,
            "form":         form,
            "active":       active,
            "action":       action,
            "page_title":   f"{action} Policy — {lt}",
            "breadcrumb": [
                {"label": "HR",                    "url": "#"},
                {"label": "Leave Policy Config",   "url": "leave:policy_config_list"},
                {"label": f"{action} — {lt}",      "url": ""},
            ],
        }


# ─────────────────────────────────────────────────────────────────
# 3. UPDATE VIEW  (edit the currently active policy IN PLACE)
#    Note: editing in place does NOT create a new version.
#    To version, use CreateView instead.
# ─────────────────────────────────────────────────────────────────

class LeavePolicyConfigUpdateView(HRAdminRequiredMixin, View):
    template_name = "leave/policy_config/form.html"

    def get(self, request, pk):
        config = get_object_or_404(LeavePolicyConfig, pk=pk)
        form   = LeavePolicyConfigForm(instance=config)
        return render(request, self.template_name,
                      self._ctx(config.leave_type, form, config, "Edit"))

    def post(self, request, pk):
        config = get_object_or_404(LeavePolicyConfig, pk=pk)
        form   = LeavePolicyConfigForm(request.POST, instance=config)

        if form.is_valid():
            obj            = form.save(commit=False)
            obj.updated_by = request.user
            try:
                obj.full_clean()
                obj.save()
                form.save_m2m()
                messages.success(request, f"Policy for '{config.leave_type}' updated.")
                return redirect("leave:policy_config_list")
            except ValidationError as e:
                form.add_error(None, e)

        return render(request, self.template_name,
                      self._ctx(config.leave_type, form, config, "Edit"))

    def _ctx(self, lt, form, config, action):
        return {
            "leave_type":   lt,
            "form":         form,
            "active":       config,
            "action":       action,
            "page_title":   f"{action} Policy — {lt}",
            "is_edit":      True,
            "breadcrumb": [
                {"label": "HR",                   "url": "#"},
                {"label": "Leave Policy Config",  "url": "leave:policy_config_list"},
                {"label": f"{action} — {lt}",     "url": ""},
            ],
        }


# ─────────────────────────────────────────────────────────────────
# 4. HISTORY VIEW  (AJAX — returns JSON for timeline modal)
# ─────────────────────────────────────────────────────────────────

class LeavePolicyConfigHistoryView(HRAdminRequiredMixin, View):

    def get(self, request, leave_type_id):
        lt       = get_object_or_404(LeaveType, pk=leave_type_id)
        versions = (
            LeavePolicyConfig.objects
            .filter(leave_type=lt)
            .order_by("-effective_from")
        )

        data = []
        for v in versions:
            data.append({
                "id":             v.pk,
                "effective_from": str(v.effective_from),
                "effective_to":   str(v.effective_to) if v.effective_to else None,
                "is_active":      v.effective_to is None,
                "created_by":     str(v.created_by) if v.created_by else "System",
                "created_at":     v.created_at.strftime("%d %b %Y, %H:%M"),
                "annual_entitlement":    v.annual_entitlement,
                "accrual_period":        v.accrual_period,
                "max_consecutive_days":  v.max_consecutive_days,
                "min_days_per_application": v.min_days_per_application,
                "max_spells_per_year":   v.max_spells_per_year,
            })

        return JsonResponse({
            "leave_type": str(lt),
            "versions":   data,
        })


# ─────────────────────────────────────────────────────────────────
# 5. COMPARE VIEW  (AJAX — returns JSON diff of two versions)
# ─────────────────────────────────────────────────────────────────

class LeavePolicyConfigCompareView(HRAdminRequiredMixin, View):

    def get(self, request):
        id_a = request.GET.get("a")
        id_b = request.GET.get("b")

        if not id_a or not id_b:
            return JsonResponse({"error": "Provide both ?a=<id>&b=<id>"}, status=400)

        config_a = get_object_or_404(LeavePolicyConfig, pk=id_a)
        config_b = get_object_or_404(LeavePolicyConfig, pk=id_b)

        dict_a = _policy_to_dict(config_a)
        dict_b = _policy_to_dict(config_b)

        # Build diff: mark each field as changed / unchanged
        diff = []
        for field, label, group in POLICY_FIELDS_LABELS:
            val_a = dict_a.get(field, {}).get("value")
            val_b = dict_b.get(field, {}).get("value")
            diff.append({
                "field":   field,
                "label":   label,
                "group":   group,
                "value_a": val_a,
                "value_b": val_b,
                "changed": val_a != val_b,
            })

        return JsonResponse({
            "leave_type": str(config_a.leave_type),
            "version_a": {
                "id":             config_a.pk,
                "effective_from": str(config_a.effective_from),
                "effective_to":   str(config_a.effective_to) if config_a.effective_to else "Present",
                "is_active":      config_a.effective_to is None,
            },
            "version_b": {
                "id":             config_b.pk,
                "effective_from": str(config_b.effective_from),
                "effective_to":   str(config_b.effective_to) if config_b.effective_to else "Present",
                "is_active":      config_b.effective_to is None,
            },
            "diff":        diff,
            "changed_count": sum(1 for d in diff if d["changed"]),
        }, encoder=DjangoJSONEncoder)