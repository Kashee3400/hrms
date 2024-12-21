from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils.timezone import make_aware, now
from hrms_app.hrms.form import *
from django.views.generic import (
    TemplateView,
)
from django.utils.timezone import localtime
from collections import defaultdict
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
)
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)
User = get_user_model()  # This gets the custom user model dynamically


class MonthAttendanceReportView(LoginRequiredMixin, TemplateView):

    template_name = "hrms_app/reports/present_absent_report.html"
    permission_denied_message = _("U are not authorized to access the page")
    title = _("Attendance Report")

    def _map_attendance_data(self, attendance_logs, leave_logs, holidays,tour_logs):
        """
        Generalized function to map both attendance and leave data with status and color under the same key.

        Args:
            attendance_logs: Queryset of AttendanceLog objects.
            leave_logs: Queryset of LeaveApplication objects.
            holidays: List of holiday objects.

        Returns:
            A nested dictionary with employee_id -> day -> data (status, color).
        """
        # Query both attendance and leave data
        attendance_logs = attendance_logs.values(
            "applied_by_id", "start_date", "att_status_short_code", "color_hex"
        )

        leave_logs = leave_logs.values(
            "appliedBy_id",
            "startDate",
            "endDate",
            "status",
            "leave_type__color_hex",
            "leave_type__leave_type_short_code",
            "leave_type__half_day_short_code",
        )
        tour_logs = leave_logs.values(
            "applied_by_id",
            "start_date",
            "end_date",
            "status",
        )

        attendance_data = defaultdict(lambda: defaultdict(list))

        # Populate the dictionary with attendance and leave data
        for log in attendance_logs:
            employee_id = log["applied_by_id"]
            day = log["start_date"].day
            attendance_data[employee_id][day].append({
                "status": log["att_status_short_code"],
                "color": log["color_hex"] or "#000000",  # Default color if None
            })
        for log in tour_logs:
            employee_id = log['applied_by_id']
            day = log['start_day'].day
            attendance_data[employee_id][day].append({
                "status": log["att_status_short_code"],
                "color": log["color_hex"] or "#000000",  # Default color if None                
            })
        for log in leave_logs:
            start_date = localtime(log["startDate"])
            employee_id = log["appliedBy_id"]
            start_day = start_date.day
            end_day = localtime(log["endDate"]).day
            for day in range(start_day, end_day + 1):
                attendance_data[employee_id][day].append({
                    "status": log["leave_type__leave_type_short_code"],
                    "color": log["leave_type__color_hex"] or "#FF0000",
                })

        holiday_days = {holiday.start_date.day: {"status": holiday.short_code, "color": holiday.color_hex} for holiday in holidays}
        for employee_id in attendance_data.keys():
            for day, holiday_info in holiday_days.items():
                attendance_data[employee_id][day].append(holiday_info)

        return attendance_data


    def _get_days_in_month(self, start_date, end_date):
        """
        Generate a list of days between the start and end date.
        """
        total_days = (end_date - start_date).days + 1
        return [start_date + timedelta(days=i) for i in range(total_days)]

    def _get_filtered_employees(self, location, active):
        """
        Return the filtered employees based on location and active status.
        """
        employees = CustomUser.objects.filter(is_active=active)
        if location:
            employees = employees.filter(device_location_id=location)

        return employees.order_by("first_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = AttendanceReportFilterForm(self.request.GET)

        if form.is_valid():
            location = self.request.GET.get("location")
            from_date = self.request.GET.get("from_date")
            to_date = self.request.GET.get("to_date")
            active = self.request.GET.get("active")
            try:
                converted_from_datetime, converted_to_datetime = self._get_date_range(
                    from_date, to_date
                )
            except ValueError:
                context["error"] = "Invalid date format. Please use YYYY-MM-DD."
                return context
            active = True if active == "on" else False
            employees = self._get_filtered_employees(location, active)

            # Fetch attendance logs for all employees in the given date range in bulk
            attendance_logs = self._get_attendance_logs(
                employees, converted_from_datetime, converted_to_datetime
            )
            leave_logs = self._get_leave_logs(
                employees, converted_from_datetime, converted_to_datetime
            )
            tour_logs = self._get_tour_logs(
                employees, converted_from_datetime, converted_to_datetime
            )
            holidays = self._get_holiday_logs(
                converted_from_datetime, converted_to_datetime
            )
            # Create a mapping of attendance data for quick lookup in the template
            attendance_data = self._map_attendance_data(
                attendance_logs=attendance_logs, leave_logs=leave_logs,holidays=holidays,tour_logs=tour_logs
            )
            context["days_in_month"] = self._get_days_in_month(
                converted_from_datetime, converted_to_datetime
            )
            context["attendance_data"] = attendance_data
            context["employees"] = employees
        else:
            context["error"] = "Please select a location and date range."
        context["form"] = form
        context["title"] = self.title
        return context

    def _get_date_range(self, from_date, to_date):
        """
        Converts the from_date and to_date strings into datetime objects.
        """
        converted_from_datetime = make_aware(datetime.strptime(from_date, "%Y-%m-%d"))
        converted_to_datetime = make_aware(datetime.strptime(to_date, "%Y-%m-%d"))
        return converted_from_datetime, converted_to_datetime

    def _get_holiday_logs(self,start_date, end_date):
        """
        Fetch all attendance logs in one query for the selected employees and date range.
        """
        return Holiday.objects.filter(
            start_date__gte=start_date, end_date__lte=end_date
        )

    def _get_attendance_logs(self, employees, start_date, end_date):
        """
        Fetch all attendance logs in one query for the selected employees and date range.
        """
        return AttendanceLog.objects.filter(
            applied_by__in=employees, start_date__gte=start_date, end_date__lte=end_date
        ).select_related("applied_by")

    def _get_leave_logs(self, employees, start_date, end_date):
        """
        Fetch all attendance logs in one query for the selected employees and date range.
        """
        return LeaveApplication.objects.filter(
            appliedBy__in=employees, startDate__gte=start_date, endDate__lte=end_date,status=settings.APPROVED
        ).select_related("appliedBy")

    def _get_tour_logs(self, employees, start_date, end_date):
        """
        Fetch all attendance logs in one query for the selected employees and date range.
        """
        return UserTour.objects.filter(
            appliedBy__in=employees, start_date__gte=start_date, end_date__lte=end_date,status=settings.APPROVED
        ).select_related("applied_by")

def format_emp_code(emp_code):
    length = len(emp_code)
    if length == 1:
        return f"00{emp_code}"
    elif length == 2:
        return f"0{emp_code}"
    else:
        return emp_code


def get_payroll_start_end_date(date):
    if date.day > 20:
        start_fetch_date = datetime(date.year, date.month - 1, 21)
        start_fetch_date = start_fetch_date.replace(hour=0, minute=1)
        end_fetch_date = datetime(date.year, date.month, 20)
        end_fetch_date = end_fetch_date.replace(hour=23, minute=59)
    else:
        # To handle the month boundary correctly
        if date.month == 1:
            start_fetch_date = datetime(date.year - 1, 12, 21)
            end_fetch_date = datetime(date.year - 1, 12, 20)
        else:
            start_fetch_date = datetime(date.year, date.month - 2, 21)
            end_fetch_date = datetime(date.year, date.month - 1, 20)
        start_fetch_date = start_fetch_date.replace(hour=0, minute=1)
        end_fetch_date = end_fetch_date.replace(hour=23, minute=59)

    return start_fetch_date, end_fetch_date
