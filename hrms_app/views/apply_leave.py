"""
views.py  —  ApplyOrUpdateLeaveView (Updated)

Changes from original
──────────────────────
1. form_valid: removed standalone validate_probation_rules() call.
   LeavePolicyManager inside the form's clean() now handles this.
   Calling it twice caused confusing duplicate errors.

2. form_valid: removed standalone validate_sufficient_balance() call.
   Same reason — LeavePolicyManager._validate_balance_sufficient()
   covers this. Only LWP (Leave Without Pay) bypasses the manager,
   and LWP has no balance to check anyway.

3. get_context_data: guarded `selected_date` usage — previously
   `leave_balance` and related lines could crash with NameError
   if leave_type was None or falsy, because `selected_date` was
   set inside the `if leave_type:` block but referenced outside it.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import FormView

from hrms_app.choices.leave import LeaveAccrualPeriod
from hrms_app.models import LeaveApplication, LeaveType
from hrms_app.forms.leave_form import LeaveApplicationForm
from hrms_app.services.leave_service import LeaveDomainService


class ApplyOrUpdateLeaveView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    model      = LeaveApplication
    form_class = LeaveApplicationForm
    template_name = "hrms_app/apply-leave.html"

    success_message_create = _("Leave applied successfully.")
    success_message_update = _("Leave updated successfully.")

    permission_action_create = "add"
    permission_action_update = "change"

    title = _("Create / Update Leave Application")

    # ─────────────────────────────────────────────────────────
    # PERMISSION CHECK
    # ─────────────────────────────────────────────────────────

    def dispatch(self, request, *args, **kwargs):
        self.object = None

        if "slug" in kwargs:
            self.object         = self.get_object()
            permission_action   = self.permission_action_update
        else:
            permission_action   = self.permission_action_create

        opts = self.model._meta
        perm = f"{opts.app_label}.{permission_action}_{opts.model_name}"

        if not request.user.has_perm(perm):
            raise PermissionDenied("You do not have permission.")

        return super().dispatch(request, *args, **kwargs)

    # ─────────────────────────────────────────────────────────
    # FORM KWARGS
    # ─────────────────────────────────────────────────────────

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["leave_type"] = (
            self.object.leave_type.id
            if self.object
            else self.kwargs.get("leave_type")
        )
        return kwargs

    # ─────────────────────────────────────────────────────────
    # FORM VALID
    # ─────────────────────────────────────────────────────────

    def form_valid(self, form):
        """
        FIX 1 + FIX 2: Removed redundant standalone calls to
        validate_probation_rules() and validate_sufficient_balance().

        Both are now handled inside LeavePolicyManager which is called
        from LeaveApplicationForm.clean(). Calling them again here
        produced duplicate, confusing error messages and ran DB queries twice.

        The only responsibility of form_valid now is:
          - attach the user and file to the instance
          - save
          - redirect
        """
        user              = self.request.user
        leave_application = form.save(commit=False)

        leave_application.appliedBy = user
        leave_application.attachment = self.request.FILES.get("attachment")
        leave_application.save()

        messages.success(
            self.request,
            self.success_message_update if self.object else self.success_message_create,
        )

        return redirect(
            reverse(
                "leave_application_detail",
                kwargs={"slug": leave_application.slug},
            )
        )

    # ─────────────────────────────────────────────────────────
    # CONTEXT DATA
    # ─────────────────────────────────────────────────────────

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user          = self.request.user
        leave_type_id = (
            self.object.leave_type.id
            if self.object
            else self.kwargs.get("leave_type")
        )
        leave_type = LeaveType.objects.filter(id=leave_type_id).first()

        # ── Defaults ──────────────────────────────────────────────────────
        today                   = timezone.now().date()
        current_period_balance  = 0
        selected_period_balance = 0
        current_period_meta     = {}
        selected_period_meta    = {}

        # FIX 3: selected_date must be defined before any reference to it.
        # Previously it was set inside `if leave_type:` but used outside,
        # causing a potential NameError when leave_type was None.
        selected_date = (
            self.object.startDate
            if self.object and self.object.startDate
            else today
        )
        # Normalize to date (startDate is DateTimeField)
        if hasattr(selected_date, "date"):
            selected_date = selected_date.date()

        leave_balance  = None
        el_count       = 0
        year_selected  = selected_date.year
        month_selected = None

        if leave_type:
            # ── Current period balance (based on today) ───────────────────
            current_period_balance = LeaveDomainService.get_remaining_balance(
                user=user,
                leave_type=leave_type,
                target_date=today,
            )
            year_today  = today.year
            month_today = (
                today.month
                if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY
                else None
            )
            current_period_meta = {
                "year":  year_today,
                "month": month_today,
            }

            # ── Selected period balance (based on leave start date) ───────
            selected_period_balance = LeaveDomainService.get_remaining_balance(
                user=user,
                leave_type=leave_type,
                target_date=selected_date,
            )
            year_selected  = selected_date.year
            month_selected = (
                selected_date.month
                if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY
                else None
            )
            selected_period_meta = {
                "year":  year_selected,
                "month": month_selected,
            }

            # ── Balance record + EL count ─────────────────────────────────
            leave_balance = LeaveDomainService.get_balance_record(
                user=user,
                leave_type=leave_type,
                target_date=selected_date,
            )
            el_count = LeaveDomainService.get_el_count(
                user=user,
                leave_type=leave_type,
            )

        context.update({
            "current_period_meta":    current_period_meta,
            "selected_period_balance":selected_period_balance,
            "selected_period_meta":   selected_period_meta,
            "object":                 self.object,
            "leave_type":             leave_type,
            "leave_balance":          leave_balance,         # FIX 3: safe — always defined above
            "rem_bal":                current_period_balance,
            "leave_year":             year_selected,
            "leave_month":            month_selected,
            "el_count":               el_count,
            "form": kwargs.get(
                "form",
                LeaveApplicationForm(
                    instance=self.object,
                    user=user,
                    leave_type=leave_type_id,
                ),
            ),
            "title": self.title,
            "urls": [
                ("home",          {"label": "Home"}),
                ("leave_tracker", {"label": "Leave Tracker"}),
            ],
        })

        return context

    # ─────────────────────────────────────────────────────────
    # GET OBJECT
    # ─────────────────────────────────────────────────────────

    def get_object(self):
        if "slug" in self.kwargs:
            return LeaveApplication.objects.get(slug=self.kwargs["slug"])
        return None