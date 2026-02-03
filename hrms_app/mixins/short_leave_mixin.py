from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from hrms_app.models import LeaveApplication,LeaveType,LeaveBalanceOpenings
from hrms_app.hrms.leave_forms import ShortLeaveApplicationForm
from django.urls import reverse
from django.utils import timezone
from hrms_app.utility.leave_utils import LeaveStatsManager
from datetime import date
from dateutil.relativedelta import relativedelta
from django.utils.dateparse import parse_date


class ShortLeaveBaseMixin(LoginRequiredMixin):
    model = LeaveApplication
    form_class = ShortLeaveApplicationForm
    template_name = "hrms_app/employee/apply_short_leave.html"
    

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        obj:LeaveApplication = form.save(commit=False)

        # 🔒 Enforce Short Leave
        obj.leave_type = LeaveType.objects.get(
            leave_type_short_code="STL"
        )

        # Short Leave is always single day
        obj.endDate = obj.startDate
        obj.appliedBy = self.request.user
        

        obj.save()
        messages.success(
            self.request,
            "Short Leave application saved successfully."
        )
        return redirect(reverse(
                    "leave_application_detail",
                    kwargs={"slug": obj.slug},
                ))
    
    def dispatch(self, request, *args, **kwargs):
        if self.kwargs.get("pk"):
            obj = get_object_or_404(
                LeaveApplication,
                pk=self.kwargs["pk"],
                user=request.user,
            )
            if obj.status in ["APPROVED", "REJECTED"]:
                messages.error(
                    request,
                    "Approved or rejected Short Leave cannot be modified."
                )
                return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)
    
    def get_selected_period(self):
        """
        Resolve period from query param 'period' (YYYY-MM-DD).
        Fallback to today.
        """
        period_str = self.request.GET.get("period")

        if period_str:
            parsed = parse_date(period_str)
            if parsed:
                return parsed

        return timezone.now().date()
    # ------------------------------------------------------------------
    # CONTEXT DATA (YEAR-AWARE)
    # ------------------------------------------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_date = self.get_selected_period()

        selected_year = selected_date.year
        selected_month = selected_date.month

        # Previous period
        previous_period_date = selected_date.replace(day=1) - relativedelta(months=1)

        previous_year = previous_period_date.year
        previous_month = previous_period_date.month

        leave_balance = LeaveBalanceOpenings.objects.filter(
            user=self.request.user,
            leave_type__leave_type_short_code="STL",
            year=selected_year,
            month=selected_month,
        ).first()

        rem_bal = 0
        pre_bal = 0

        if leave_balance:
            stats = LeaveStatsManager(
                user=self.request.user,
                leave_type=leave_balance.leave_type,
            )

            rem_bal = stats.get_remaining_balance(
                year=selected_year,
                month=selected_month
            )

            pre_bal = stats.get_remaining_balance(
                year=previous_year,
                month=previous_month
            )

        context.update(
            {
                "leave_balance": leave_balance,
                "rem_bal": rem_bal,
                "pre_bal": pre_bal,
                "leave_year": selected_year,
                "leave_month": selected_month,
                "prev_year": previous_year,
                "prev_month": previous_month,
                "selected_date": selected_date,
                "object": self.object,
                "title": self.title,
                "urls": [
                    ("home", {"label": "Home"}),
                    ("leave_tracker", {"label": "Leave Tracker"}),
                ],
            }
        )

        return context
