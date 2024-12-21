from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils.timezone import make_aware, now, localtime
from hrms_app.hrms.form import *
from django.views.generic import (
    TemplateView,
)
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

    def _map_attendance_data(
        self,
        attendance_logs,
        leave_logs,
        holidays,
        tour_logs,
        start_date_object,
        end_date_object,
    ):
        attendance_data = defaultdict(lambda: defaultdict(list))

        # Optimized Holiday Handling
        holiday_days = {
            holiday.start_date.day: {
                "status": holiday.short_code,
                "color": holiday.color_hex,
            }
            for holiday in holidays
        }

        # Optimize Attendance Log Mapping
        for log in attendance_logs:
            attendance_data[log.applied_by.id][log.start_date.day].append(
                {
                    "status": log.att_status_short_code,
                    "color": log.color_hex or "#000000",
                    "start_date": log.start_date,
                    "end_date": log.end_date,
                }
            )

        # Optimize Tour Log Mapping
        for log in tour_logs:
            for day in range((log.end_date - log.start_date).days + 1):
                current_date = log.start_date + timedelta(days=day)
                day_of_month = current_date.day
                attendance_data[log.applied_by.id][day_of_month].append(
                    {
                        "status": log.short_code,
                        "color": "#06c1c4",
                        "start_date": log.start_date,
                        "end_date": log.end_date,
                        "start_time": log.start_time,
                        "end_time": log.end_time,
                    }
                )
                # Remove holiday if tour is available for the day
                holiday_days.pop(day_of_month, None)
        # Add remaining holidays to attendance data
        for employee_id in attendance_data.keys():
            for day, holiday_info in holiday_days.items():
                attendance_data[employee_id][day].append(holiday_info)

        # Optimize Leave Log Mapping
        for log in leave_logs:
            start_date = localtime(log.startDate)
            end_date = localtime(log.endDate)
            for day in range((end_date - start_date).days + 1):
                current_date = start_date + timedelta(days=day)
                day_of_month = current_date.day
                leave_status = log.leave_type.leave_type_short_code
                if leave_status == "CL":
                    if day_of_month in holiday_days:
                        attendance_data[log.appliedBy.id][day_of_month].append(
                            {
                                "status": "",
                                "color": holiday_days[day_of_month]["color"],
                            }
                        )
                    elif current_date.weekday() == 6:
                        attendance_data[log.appliedBy.id][day_of_month].append(
                            {
                                "status": "OFF",
                                "color": "#CCCCCC",
                            }
                        )
                    else:
                        attendance_data[log.appliedBy.id][day_of_month].append(
                            {
                                "status": leave_status,
                                "color": log.leave_type.color_hex or "#FF0000",
                            }
                        )
                else:
                    if day_of_month in attendance_data[log.appliedBy.id]:
                        # Check if any entry has the status 'FH'
                        for entry in attendance_data[log.appliedBy.id][day_of_month]:
                            if entry.get("status") == "FH":
                                del attendance_data[log.appliedBy.id][day_of_month]
                                break
                    attendance_data[log.appliedBy.id][day_of_month].append(
                        {
                            "status": leave_status,
                            "color": log.leave_type.color_hex or "#FF0000",
                        }
                    )

        # Efficient Sunday Handling
        sundays = {
            day
            for day in range(start_date_object.day, end_date_object.day + 1)
            if (start_date_object + timedelta(days=day - 1)).weekday() == 6
        }

        for employee_id in attendance_data.keys():
            for sunday in sundays:
                if not attendance_data[employee_id][sunday]:
                    attendance_data[employee_id][sunday].append(
                        {
                            "status": "OFF",
                            "color": "#CCCCCC",  # Default color for "OFF"
                        }
                    )

        return attendance_data

    def _get_days_in_month(self, start_date, end_date):
        return [
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
        ]

    def _get_filtered_employees(self, location, active):
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

            attendance_data = self._map_attendance_data(
                attendance_logs=attendance_logs,
                leave_logs=leave_logs,
                holidays=holidays,
                tour_logs=tour_logs,
                start_date_object=converted_from_datetime,
                end_date_object=converted_to_datetime,
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
        converted_from_datetime = make_aware(datetime.strptime(from_date, "%Y-%m-%d"))
        converted_to_datetime = make_aware(datetime.strptime(to_date, "%Y-%m-%d"))
        return converted_from_datetime, converted_to_datetime

    def _get_holiday_logs(self, start_date, end_date):
        return Holiday.objects.filter(
            start_date__gte=start_date, end_date__lte=end_date
        )

    def _get_attendance_logs(self, employees, start_date, end_date):
        return AttendanceLog.objects.filter(
            applied_by__in=employees, start_date__gte=start_date, end_date__lte=end_date
        )

    def _get_leave_logs(self, employees, start_date, end_date):
        return LeaveApplication.objects.filter(
            appliedBy__in=employees,
            startDate__gte=start_date,
            endDate__lte=end_date,
            status=settings.APPROVED,
        )

    def _get_tour_logs(self, employees, start_date, end_date):
        return UserTour.objects.filter(
            applied_by__in=employees,
            start_date__gte=start_date,
            end_date__lte=end_date,
            status=settings.APPROVED,
        )
