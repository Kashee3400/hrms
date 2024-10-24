from hrms_app.hrms.form import *
from hrms_app.models import *
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.contrib import messages
from django.views.generic import (
    FormView,
    DetailView,
    CreateView,
    TemplateView,
    UpdateView,
    DeleteView,
)
from django.shortcuts import render
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
    PermissionRequiredMixin,
)
import pandas as pd
from django.urls import reverse, reverse_lazy
from hrms_app.views.mixins import LeaveListViewMixin
from django.utils.translation import gettext_lazy as _
from datetime import datetime
from django.conf import settings
from urllib.parse import urlparse
from django.shortcuts import get_object_or_404
from hrms_app.utility.leave_utils import get_employee_requested_leave
from django.utils.timezone import make_naive
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
import logging
from django.core.files.storage import FileSystemStorage
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.views import View
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_date"] = datetime.now()
        urls = [
            ("dashboard", {"label": "Dashboard"}),
        ]
        context["urls"] = urls
        return context

    def get(self, request, *args, **kwargs):
        # Add your GET request handling logic here
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Add your POST request handling logic here
        return super().post(request, *args, **kwargs)


class EmployeeProfileView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    template_name = "hrms_app/profile.html"
    model = CustomUser
    context_object_name = "employee"
    permission_required = "hrms_app.view_employeeprofileview"
    def test_func(self):
        return self.get_object() == self.request.user or self.request.user.is_staff

    def get_object(self, queryset=None):
        user_id = self.kwargs.get("pk")
        if user_id:
            return get_object_or_404(CustomUser, id=user_id)
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(self.request.user)
        context["current_date"] = datetime.now()
        urls = [
            ("dashboard", {"label": "Dashboard"}),
        ]
        context["urls"] = urls
        return context

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AboutPageView(TemplateView):
    template_name = "hrms_app/calendar.html"


class LeaveTrackerView(PermissionRequiredMixin, TemplateView):
    template_name = "hrms_app/leave-tracker.html"
    permission_required = "hrms_app.view_leaveapplication"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        form = FilterForm(self.request.GET)

        # Fetch leave balances
        leave_types = LeaveType.objects.all()
        leave_balances = LeaveBalanceOpenings.objects.filter(
            user=user, leave_type__in=leave_types
        )
        leave_balances_dict = {lb.leave_type: lb for lb in leave_balances}
        leave_balances_list = [
            {
                "balance": lb.remaining_leave_balances,
                "leave_type": lb.leave_type,
                "url": reverse("apply_leave_with_id", args=[lb.leave_type.pk]),
                "color": f"{lb.leave_type.color_hex}",
            }
            for lb in leave_balances
        ]

        if user.personal_detail and user.personal_detail.gender.gender == "Female":
            ml_balance = leave_balances_dict.get(settings.ML)
            if ml_balance:
                leave_balances_list.append(
                    {
                        "balance": ml_balance.remaining_leave_balances,
                        "leave_type": ml_balance.leave_type.leave_type,
                        "url": reverse(
                            "apply_leave_with_id", args=[ml_balance.leave_type.id]
                        ),
                        "color": "#ff9447",
                    }
                )

        # Start with an initial QuerySet for leaves
        leaves = LeaveApplication.objects.filter(
            appliedBy__in=user.employees.all(), status=settings.PENDING
        )

        if form.is_valid():
            selected_status = form.cleaned_data.get("status", settings.PENDING)
            from_date = form.cleaned_data.get("fromDate")
            to_date = form.cleaned_data.get("toDate")

            if selected_status:
                leaves = leaves.filter(status=selected_status)
            if from_date:
                leaves = leaves.filter(startDate__gte=from_date)
            if to_date:
                leaves = leaves.filter(endDate__lte=to_date)

        context.update(
            {
                "current_date": datetime.now(),
                "leave_balances": leave_balances_list,
                "form": form,
                "selected_status": selected_status,
                "employee_leaves": [
                    {
                        "leaveApplication": leave,
                        "start_date": format_date(leave.startDate),
                        "end_date": format_date(leave.endDate),
                    }
                    for leave in leaves
                ],
                "pending_leave_count": len(
                    get_employee_requested_leave(user=user, status=settings.PENDING)
                ),
            }
        )

        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("leave_tracker", {"label": "Leave Tracker"}),
        ]
        context["urls"] = urls

        return context


class ApplyLeaveView(CreateView):
    model = LeaveApplication
    form_class = LeaveApplicationForm
    template_name = "hrms_app/apply-leave.html"
    permission_required = "hrms_app.add_leaveapplication"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["leave_type"] = self.kwargs.get("pk")
        return kwargs

    def form_valid(self, form):
        leave_application = form.save(commit=False)
        leave_application.appliedBy = self.request.user
        leave_application.save()
        messages.success(self.request, "Leave applied successfully")
        next_url = self.request.POST.get("next")
        if next_url and urlparse(next_url).netloc == "":
            return redirect(next_url)
        return redirect(reverse_lazy("leave_tracker"))

    def form_invalid(self, form):
        leave_type = self.kwargs.get("pk")
        leave_balance = LeaveBalanceOpenings.objects.filter(
            user=self.request.user, leave_type_id=leave_type
        ).first()
        context = self.get_context_data(form=form, leave_balance=leave_balance)
        messages.success(self.request, "Leave application failed")
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leave_type = kwargs.get("leave_type", self.kwargs.get("pk"))
        leave_balance = kwargs.get(
            "leave_balance",
            LeaveBalanceOpenings.objects.filter(
                user=self.request.user, leave_type_id=leave_type
            ).first(),
        )
        context["form"] = kwargs.get(
            "form", LeaveApplicationForm(user=self.request.user, leave_type=leave_type)
        )
        context["leave_balance"] = leave_balance
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("leave_tracker", {"label": "Leave Tracker"}),
        ]
        context["urls"] = urls
        return context


class LeaveApplicationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = LeaveApplication
    form_class = LeaveStatusUpdateForm
    template_name = "hrms_app/leave_application_detail.html"
    permission_required = "hrms_app.change_leaveapplication"
    permission_denied_message = (
        "You do not have permission to update the LeaveApplication."
    )

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_object(self, queryset=None):
        return get_object_or_404(LeaveApplication, slug=self.kwargs.get("slug"))

    def form_valid(self, form):
        response = super().form_valid(form)
        leave_application = form.instance
        action_by = self.request.user
        if leave_application.status == settings.APPROVED:
            LeaveLog.create_log(leave_application, action_by, settings.APPROVED)
        elif leave_application.status == settings.REJECTED:
            LeaveLog.create_log(leave_application, action_by, settings.REJECTED)
        elif leave_application.status == settings.CANCELLED:
            LeaveLog.create_log(leave_application, action_by, settings.CANCELLED)
        else:
            LeaveLog.create_log(leave_application, action_by, "Updated")
        messages.success(self.request, _("Leave application updated successfully"))
        return response

    def get_success_url(self):
        return reverse_lazy(
            "leave_application_detail", kwargs={"slug": self.object.slug}
        )


class LeaveApplicationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = LeaveApplication
    template_name = "hrms_app/leave_application_detail.html"
    context_object_name = "leave_application"
    permission_denied_message = _("You do not have permission to access this page.")
    permission_required = "hrms_app.view_leaveapplication"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_object(self, queryset=None):
        leave_application = super().get_object(queryset)
        user = self.request.user

        if (
                leave_application.appliedBy == user
                or leave_application.appliedBy.reports_to == user
        ):
            return leave_application

        # If neither, raise a permission denied exception
        raise PermissionDenied(
            "You do not have permission to view this leave application."
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leave_application = self.get_object()
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("leave_tracker", {"label": "Leave Tracker"}),
            (
                "leave_application_detail",
                {
                    "label": f"{leave_application.applicationNo}",
                    "slug": leave_application.slug,
                },
            ),
        ]
        context["is_manager"] = (
                self.request.user == leave_application.appliedBy.reports_to
        )
        context["status_form"] = LeaveStatusUpdateForm(
            user=self.request.user, instance=self.object
        )
        context["urls"] = urls
        return context


from hrms_app.utility.leave_utils import format_date
from django.http import JsonResponse
from django.views import View

class LeaveApplicationListView(View,LeaveListViewMixin):
    START_LEAVE_TYPE_CHOICES = {
        "1": "Full Day",
        "2": "First Half (Morning)",
        "3": "Second Half (Afternoon)",
    }

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "User not authenticated"}, status=401)

        leave_applications = [
            {
                "name": f"{leaveApplication.appliedBy.first_name} {leaveApplication.appliedBy.last_name}",
                "applicationNo": leaveApplication.applicationNo,
                "leave_type": leaveApplication.leave_type.leave_type,
                "startDate": format_date(leaveApplication.startDate),
                "startDayChoice": self.START_LEAVE_TYPE_CHOICES.get(
                    leaveApplication.startDayChoice, leaveApplication.startDayChoice
                ),
                "endDate": format_date(leaveApplication.endDate),
                "endDayChoice": self.START_LEAVE_TYPE_CHOICES.get(
                    leaveApplication.endDayChoice, leaveApplication.endDayChoice
                ),
                "usedLeave": leaveApplication.usedLeave,
                "status": leaveApplication.status.capitalize(),
            }
            for leaveApplication in request.user.leaves.all()
        ]

        data = {
            "header": self.get_headers(),  # Assuming get_headers() is still applicable
            "data": leave_applications,
        }

        return JsonResponse(data)

class EventPageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "hrms_app/calendar.html"
    permission_required = "hrms_app.view_attendancelog"
    permission_denied_message = _("You do not have permission to access this page.")

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("calendar", {"label": "Attendance Calendar"}),
        ]
        context["urls"] = urls
        return context


class EventDetailPageView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = AttendanceLog
    template_name = "hrms_app/event_detail.html"
    form_class = AttendanceLogForm
    slug_field = "slug"
    slug_url_kwarg = "slug"
    permission_required = "hrms_app.change_attendancelog"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_object(self, queryset=None):
        attendance_log = super().get_object(queryset)
        user = self.request.user

        if (
                attendance_log.applied_by == user
                or attendance_log.applied_by.reports_to == user
        ):
            return attendance_log
        raise PermissionDenied()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        attendance_log = self.get_object()
        kwargs["user"] = self.request.user
        kwargs["is_manager"] = self.request.user == attendance_log.applied_by.reports_to
        return kwargs

    def form_valid(self, form):
        form.instance.is_submitted = True
        self.object = form.save()
        self.object.add_action(
            action=self.object.status,
            performed_by=self.request.user,
            comment=f"Approved By : {self.request.user.get_username()}",
        )
        messages.success(self.request, "Regularization Updated Successfully")
        return HttpResponseRedirect(
            reverse("event_detail", kwargs={"slug": self.object.slug})
        )

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attendance_log = self.get_object()
        context["is_manager"] = (
                self.request.user == attendance_log.applied_by.reports_to
        )
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("calendar", {"label": "Attendance"}),
            (
                "event_detail",
                {"label": f"{attendance_log.title}", "slug": attendance_log.slug},
            ),
        ]
        context["urls"] = urls
        return context


class EventListView(View):
    def get(self, request, *args, **kwargs):
        holidays = Holiday.objects.all()
        attendances = AttendanceLog.objects.filter(applied_by=request.user)
        leave_applications = LeaveApplication.objects.filter(appliedBy=request.user)
        tour_applications = UserTour.objects.filter(applied_by=request.user)
        events_data = [
            {
                "id": holiday.pk,
                "title": holiday.title,
                "start": holiday.start_date,
                "end": holiday.end_date,
                "color": holiday.color_hex,
                "url": "#!",
            }
            for holiday in holidays
        ]
        events_data.extend(
            {
                "id": tour.pk,
                "title": f"Tour -> {tour.approval_type}",
                "start": f"{tour.start_date} {tour.start_time}",
                "end": f"{tour.end_date} {tour.end_time}",
                "url": reverse_lazy(
                    "tour_application_detail", kwargs={"slug": tour.slug}
                ),
            }
            for tour in tour_applications
        )
        events_data.extend(
            {
                "id": leave.pk,
                "title": leave.leave_type.leave_type,
                "start": leave.startDate,
                "end": leave.endDate,
                "color": leave.leave_type.color_hex,
                "url": reverse_lazy(
                    "leave_application_detail", kwargs={"slug": leave.slug}
                ),
            }
            for leave in leave_applications
        )
        for att in attendances:
            events_data.append(
                {
                    "id": att.pk,
                    "title": att.att_status,
                    "start": make_naive(att.start_date).date(),
                    "end": make_naive(att.end_date).date(),
                    "color": att.color_hex,
                    "url": reverse_lazy("event_detail", kwargs={"slug": att.slug}),
                }
            )
            if att.reg_status is not None:
                events_data.append(
                    {
                        "id": att.pk,
                        "title": att.reg_status,
                        "start": make_naive(att.start_date),
                        "end": make_naive(att.end_date),
                        "url": reverse_lazy("event_detail", kwargs={"slug": att.slug}),
                    }
                )

        return JsonResponse(events_data, safe=False)


class ProfilePageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "hrms_app/profile.html"
    permission_required = "hrms_app.view_personaldetails"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_context_data(self, **kwargs):
        pd = None
        if PersonalDetails.objects.filter(user=self.request.user).exists():
            pd = PersonalDetails.objects.get(user=self.request.user)
        print(self.request.user)
        context = super().get_context_data(**kwargs)
        context["current_date"] = datetime.now()
        context["pd"] = pd
        return context


class ChangePasswordView(LoginRequiredMixin, FormView):
    template_name = "hrms_app/change-password.html"
    form_class = ChangeUserPasswordForm
    success_url = reverse_lazy("login")
    error_message = "Error while changing the password. Please try again"

    def form_valid(self, form):
        custom_user = self.request.user
        custom_user.is_password_changed = True
        custom_user.save()
        form.save()
        messages.success(
            self.request,
            "Your password was changed successfully. Please Login again to continue...",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, self.error_message)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["error_message"] = self.error_message
        context["form_errors"] = self.get_form().errors  # Corrected line
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


def check_user_balance(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Method not allowed"})
    leaveType = request.POST.get("leaveType")
    leave_bal = 0
    if LeaveBalanceOpenings.objects.filter(
            user=request.user, leave_type=leaveType
    ).exists():
        leave = LeaveBalanceOpenings.objects.get(
            user=request.user, leave_type=leaveType
        )
        if leave.leave_type.leave_type in [settings.UP, settings.ML]:
            leave_bal = 1
        else:
            leave_bal = leave.balance
    return JsonResponse({"success": True, "balance": leave_bal, "type": leaveType})


class AddHolidaysView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Holiday
    template_name = "invent_app/feedback_form.html"
    success_url = reverse_lazy("add_holidays")
    permission_required = "hrms_app.add_holidays"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        holidays = Holiday.objects.all()
        context["form"] = self.get_form()
        context["holidays"] = holidays
        return context

    def post(self, request):
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES["file"]
            Holiday.objects.all().delete()
            try:
                df = pd.read_excel(excel_file)
                for index, row in df.iterrows():
                    try:
                        date_str = row["Date"]
                        formatted_start_date = date_str.strftime("%Y-%m-%d")
                    except ValueError as e:
                        error_message = f"Error converting date: {e}"
                        return render(
                            request,
                            "hrms_app/holidays.html",
                            {"form": form, "error_message": error_message},
                        )
                    holiday = Holiday.objects.create(
                        title=row["Holiday Name"],
                        date=formatted_start_date,
                    )
                    holiday.save()
                messages.success(request, "Holidays uploaded successfully")
                return redirect("add_holidays")

            except Exception as e:
                error_message = f"Error: {e}"
                messages.error(request, "Error Occurred. Please try again later.")
                form = ExcelUploadForm()
                return render(request, "hrms_app/holidays.html", {"form": form})
        else:
            messages.error(request, "Error Occurred. Please try again later.")
            return redirect("add_holidays")

    def get_success_url(self):
        """
        Return the URL to redirect to after processing a valid form.
        """
        return self.success_url


class TourTrackerView(PermissionRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "hrms_app/tour-tracker.html"
    permission_required = "hrms_app.add_usertour"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        form = FilterForm(self.request.GET)

        # Start with an initial QuerySet for leaves
        tours = UserTour.objects.filter(applied_by__in=user.employees.all())

        if form.is_valid():
            selected_status = form.cleaned_data.get("status", settings.PENDING)
            from_date = form.cleaned_data.get("fromDate")
            to_date = form.cleaned_data.get("toDate")
            if not selected_status:
                tours = tours.filter(status=settings.PENDING)
            if selected_status:
                tours = tours.filter(status=selected_status)
            if from_date:
                tours = tours.filter(startDate__gte=from_date)
            if to_date:
                tours = tours.filter(endDate__lte=to_date)

        context.update(
            {
                "current_date": datetime.now(),
                "form": form,
                "objects": tours,
                "selected_status": selected_status,
            }
        )

        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("tour_tracker", {"label": "Tour Tracker"}),
        ]
        context["urls"] = urls
        return context


class ApplyTourView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = UserTour
    form_class = TourForm
    template_name = "hrms_app/apply-tour.html"
    success_url = reverse_lazy("tour_tracker")
    permission_required = "hrms_app.add_usertour"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("tour_tracker", {"label": "Tour Tracker"}),
            (
                "apply_tour",
                {"label": "Tour Application"},
            ),
        ]
        context["urls"] = urls
        return context

    def form_valid(self, form):
        tour = form.save(commit=False)
        tour.applied_by = self.request.user
        tour.save()
        messages.success(self.request, "Tour Applied Successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class TourApplicationDetailView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = UserTour
    template_name = "hrms_app/tour_application_detail.html"
    context_object_name = "tour_application"
    permission_required = "hrms_app.view_usertour"
    form_class = TourStatusUpdateForm
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_object(self, queryset=None):
        tour_application = super().get_object(queryset)
        user = self.request.user
        if (
                tour_application.applied_by == user
                or tour_application.applied_by.reports_to == user
        ):
            return tour_application
        return HttpResponseForbidden(
            "Only Employee and Manager can view His/Her tour details."
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tour_application = self.get_object()
        kwargs["user"] = self.request.user
        kwargs["is_manager"] = (
                self.request.user == tour_application.applied_by.reports_to
        )
        return kwargs

    def form_valid(self, form):
        # if not form.cleaned_data.get('status'):
        #     return self.form_invalid(form, _('Please select status.'))
        self.object = form.save()
        messages.success(
            self.request,
            f"Regularization {form.cleaned_data.get('status')} Successfully",
        )
        return HttpResponseRedirect(
            reverse("event_detail", kwargs={"slug": self.object.slug})
        )

    def form_invalid(self, form, msg=None):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tour_application = self.get_object()
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("tour_tracker", {"label": "Tour Tracker"}),
            (
                "tour_application_detail",
                {"label": f"{tour_application.slug}", "slug": tour_application.slug},
            ),
        ]
        context["is_manager"] = (
                self.request.user == tour_application.applied_by.reports_to
        )
        context["urls"] = urls
        return context


class TourApplicationDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = UserTour
    permission_required = "hrms_app.delete_usertour"
    success_url = reverse_lazy("tour_tracker")

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def post(self, request, *args, **kwargs):
        # Call the superclass method to handle the deletion
        response = super().post(request, *args, **kwargs)
        messages.error(request, "Tour application deleted successfully.")
        return response

    def get_success_url(self):
        return self.success_url


class TourApplicationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = UserTour
    form_class = TourStatusUpdateForm
    template_name = "hrms_app/tour_application_detail.html"
    permission_required = "hrms_app.change_usertour"

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def get_object(self, queryset=None):
        return get_object_or_404(UserTour, slug=self.kwargs.get("slug"))

    def form_valid(self, form):
        response = super().form_valid(form)
        tour_application = form.instance
        reason = form.cleaned_data.get("reason")
        action_by = self.request.user
        if tour_application.status == settings.APPROVED:
            tour_application.approve(action_by=action_by, reason=reason)
        elif tour_application.status == settings.REJECTED:
            tour_application.reject(action_by=action_by, reason=reason)
        elif tour_application.status == settings.CANCELLED:
            tour_application.cancel(action_by=action_by, reason=reason)
        elif tour_application.status == settings.COMPLETED:
            tour_application.complete(action_by=action_by, reason=reason)
        elif tour_application.status == settings.EXTENDED:
            tour_application.extend(action_by=action_by, reason=reason)
        elif tour_application.status == settings.PENDING_CANCELLATION:
            TourStatusLog.create_log(
                tour=tour_application,
                action_by=action_by,
                action="Cancellation request",
                comments=reason,
            )
        else:
            TourStatusLog.create_log(
                tour=tour_application,
                action_by=action_by,
                action="Updated",
                comments=reason,
            )
        messages.success(self.request, "Tour status updated successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy(
            "tour_application_detail", kwargs={"slug": self.object.slug}
        )


class UploadBillView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = BillForm
    template_name = "hrm_app/upload_bill.html"

    def get_success_url(self):
        return reverse_lazy("tour_detail", kwargs={"slug": self.kwargs["slug"]})

    def form_valid(self, form):
        tour = get_object_or_404(UserTour, pk=self.kwargs["pk"])
        bill = form.save(commit=False)
        bill.tour = tour
        bill.save()
        tour.bills_submitted = True
        tour.save()
        return super().form_valid(form)

    def test_func(self):
        tour = get_object_or_404(UserTour, pk=self.kwargs["pk"])
        return self.request.user == tour.applied_by


class CustomUploadView(View):
    @csrf_exempt
    def post(self, request, *args, **kwargs):
        file = request.FILES.get("upload")
        if file:
            file_name = default_storage.save(file.name, ContentFile(file.read()))
            file_url = default_storage.url(file_name)
            response = {
                "url": file_url,
                "uploaded": True,
                "message": "File uploaded successfully",
            }
        else:
            response = {"uploaded": False, "message": "No file uploaded"}
        return JsonResponse(response)


from formtools.wizard.views import SessionWizardView

FORMS = [
    ("user", CustomUserForm),
    ("personal", PersonalDetailsForm),
    ("paddress", PermanentAddressForm),
    ("caddress", CorrespondingAddressForm),
]

TEMPLATES = {
    "user": "hrms_app/wizard/user_form.html",
    "personal": "hrms_app/wizard/personal_details_form.html",
    "paddress": "hrms_app/wizard/paddress_form.html",
    "caddress": "hrms_app/wizard/caddress_form.html",
}


class UserCreationWizard(SessionWizardView):
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    template_name = "hrms_app/form_wizard.html"
    url_name = reverse_lazy("/")

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_user_instance(self):
        user_id = self.kwargs.get("pk")
        return get_object_or_404(CustomUser, pk=user_id) if user_id else None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("create_user", {"label": "Create Employee"}),
        ]
        context["urls"] = urls
        return context

    def get_form_initial(self, step):
        user = self.get_user_instance()
        if user:
            progress = FormProgress.objects.filter(user=user, step=step).first()
            if progress:
                return progress.data

            model_class = self.form_list[step]._meta.model
            instance = None

            if model_class == CustomUser:
                instance = model_class.objects.filter(pk=user.pk).first()
            else:
                instance = model_class.objects.filter(user_id=user.pk).first()

            return model_to_dict(instance) if instance else None

        return super().get_form_initial(step)

    def post(self, *args, **kwargs):
        current_step = self.steps.current
        user = self.get_user_instance()

        if "wizard_goto_step" in self.request.POST:
            return self.render_goto_step(self.request.POST["wizard_goto_step"])

        form = self.get_form(
            current_step, data=self.request.POST, files=self.request.FILES
        )
        if form.is_valid():
            if user:
                self.save_form_data(user, current_step, form.cleaned_data)
            return super().post(*args, **kwargs)

        return self.render(form)

    def save_form_data(self, user, current_step, form_data):
        try:
            FormProgress.objects.update_or_create(
                user=user, step=current_step, defaults={"data": form_data}
            )
        except IntegrityError as e:
            logger.error(f"Error saving form data for step {current_step}: {e}")
            raise

    def done(self, form_list, **kwargs):
        try:
            with transaction.atomic():
                return self._extracted_from_done_4(form_list)
        except Exception as e:
            logger.error(f"Error during form submission in done method: {e}")
            return self.render_error_page()

    def _extracted_from_done_4(self, form_list):
        user_form = form_list[0]
        personal_details_form = form_list[1]
        paddress_form = form_list[2]
        caddress_form = form_list[3]
        user = self.get_user_instance()
        if not user:
            user = user_form.save(commit=False)
            user.set_password("12345@Kmpcl")
            user.save()

        # Save all the other form data
        personal_details = personal_details_form.save(commit=False)
        personal_details.user = user
        personal_details.save()

        paddress = paddress_form.save(commit=False)
        paddress.user = user
        paddress.save()

        caddress = caddress_form.save(commit=False)
        caddress.user = user
        caddress.save()

        FormProgress.objects.filter(user=user).update(status="completed")
        return redirect("employees")

    def render_error_page(self):
        return redirect("error_page")


from django.shortcuts import redirect


def cancel_user_creation(request):
    request.session.pop("current_step", None)
    return redirect("/")


from django.views.generic import ListView
from django.db.models import Q


class EmployeeListView(LoginRequiredMixin, ListView):
    model = CustomUser
    template_name = (
        "hrms_app/employee/employees.html"  # Template for rendering user list
    )
    context_object_name = "users"
    paginate_by = 10  # Pagination limit

    def get_queryset(self):
        queryset = CustomUser.objects.all()

        # Filter by active status if provided in GET params
        is_active = self.request.GET.get("is_active")
        if is_active is not None and is_active != "":
            queryset = queryset.filter(is_active=is_active)
        elif is_active == "":
            queryset = queryset

        # Search by username, first name, last name, or email
        search_query = self.request.GET.get("q")
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(official_email__icontains=search_query)
            )

        return queryset.order_by("-date_joined")  # Sort by date joined by default

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass search query and is_active filter to the context for form persistence
        context["search_query"] = self.request.GET.get("q", "")
        context["is_active"] = self.request.GET.get("is_active", "")
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("employees", {"label": "Employee List"}),
        ]
        context["urls"] = urls
        return context


