from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from hrms_app.models import LeaveApplication,LeaveType,LeaveBalanceOpenings
from hrms_app.hrms.leave_forms import ShortLeaveApplicationForm
from django.urls import reverse
from django.utils import timezone
from hrms_app.utility.leave_utils import LeaveStatsManager


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
        return redirect(self.get_success_url())
    
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
    
    def get_success_url(self):
        return reverse(
            "leave_application_detail",
            kwargs={"slug": self.object.slug},
        )
        
    def get_selected_year(self):
        """
        Resolve leave year from query param.
        Fallback to current year.
        """
        try:
            return int(self.request.GET.get("year", timezone.now().year))
        except (TypeError, ValueError):
            return timezone.now().year


    # ------------------------------------------------------------------
    # CONTEXT DATA (YEAR-AWARE)
    # ------------------------------------------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_year = self.get_selected_year()

        leave_balance = LeaveBalanceOpenings.objects.filter(
            user=self.request.user,
            leave_type__leave_type_short_code="STL",
            year=selected_year,
        ).first()

        el_count = 0
        rem_bal = 0

        if leave_balance:
            stats = LeaveStatsManager(
                user=self.request.user,
                leave_type=leave_balance.leave_type,
            )
            rem_bal = stats.get_remaining_balance(year=selected_year)
        
        context.update(
            {
                "leave_balance": leave_balance,
                "rem_bal": rem_bal,
                "leave_year": selected_year,
                "object": self.object,
                "el_count": el_count,
                "title": self.title,
                "urls": [
                    ("home", {"label": "Home"}),
                    ("leave_tracker", {"label": "Leave Tracker"}),
                ],
            }
        )

        return context
