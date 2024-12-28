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
from django.db.models import Prefetch

logger = logging.getLogger(__name__)
User = get_user_model()


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

        # # Optimize Attendance Log Mapping
        # for log in attendance_logs:
        #     attendance_data[log.applied_by.id][log.start_date.day].append(
        #         {
        #             "status": log.att_status_short_code,
        #             "color": log.color_hex or "#000000",
        #         }
        #     )
        # Optimize Attendance Log Mapping
        for log in attendance_logs:
            attendance_data[log.applied_by.id][log.start_date.day].append(
                {
                    "status": log.att_status_short_code,
                    "color": log.color_hex or "#000000",
                }
            )

        # Optimize Tour Log Mapping
        for log in tour_logs:
            daily_durations = calculate_daily_tour_durations(log.start_date, log.start_time, log.end_date, log.end_time)
            for date, short_code, duration in daily_durations:
                attendance_data[log.applied_by.id][date.day] = {
                        "status": short_code,
                        "color": "#06c1c4",
                    }
            holiday_days.pop(date.day, None)

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


class DetailedMonthlyPresenceView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/reports/present_absent_detailed_report.html"
    permission_denied_message = _("U are not authorized to access the page")
    title = _("Attendance Detailed Report")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = AttendanceReportFilterForm(self.request.GET)
        if form.is_valid():
            location = self.request.GET.get("location")
            from_date = self.request.GET.get("from_date")
            to_date = self.request.GET.get("to_date")
            active = self.request.GET.get("active")
            active = True if active == "on" else False
            table_data = get_monthly_presence_html_table(
                converted_from_datetime=from_date,
                converted_to_datetime=to_date,
                is_active=active,
                location=location,
            )
            context.update({"html_table": table_data, "form": form})
        context.update({"title": self.title, "form": form})
        return context


def get_monthly_presence_html_table(
    converted_from_datetime, converted_to_datetime, is_active, location
):
    monthly_presence_data = generate_monthly_presence_data_detailed(
        converted_from_datetime, converted_to_datetime, is_active, location
    )
    converted_from_datetime = datetime.strptime(converted_from_datetime, "%Y-%m-%d")
    converted_to_datetime = datetime.strptime(converted_to_datetime, "%Y-%m-%d")
    date_range = [
        (converted_from_datetime + timedelta(days=day)).date()
        for day in range((converted_to_datetime - converted_from_datetime).days + 1)
    ]

    # HTML table construction
    headers = ["Employee Code", "Name", "Attendance"] + [
        f"{day.day}-{day.strftime('%b')}" for day in date_range
    ]
    table_html = (
        '<div class="table-container"><table class="rtable table-bordered">'
        "<thead><tr>"
        + "".join(f'<th class="sticky-header">{header}</th>' for header in headers)
        + "</tr></thead><tbody>"
    )

    users = User.objects.filter(is_active=is_active).select_related("personal_detail")
    for user in users:
        emp_code = user.personal_detail.employee_code
        if emp_code in monthly_presence_data:
            row_data = {
                "status": f'<tr><td class="sticky-col" rowspan="6">KMPCL-{format_emp_code(emp_code)}</td><td class="sticky-col" rowspan="6">{user.get_full_name()}</td><td>Status</td>',
                "in_time": "<tr><td>In Time</td>",
                "out_time": "<tr><td>Out Time</td>",
                "total_duration": "<tr><td>Duration</td>",
                "leave": "<tr><td>Leave</td>",
                "tour": "<tr><td>Tour</td>",
            }

            for day_date in date_range:
                day_str = day_date.strftime("%Y-%m-%d")
                cell_data = get_cell_data(
                    user, day_date, day_str, monthly_presence_data, emp_code
                )
                for row_type in row_data.keys():
                    style = get_style(row_type, cell_data)
                    row_data[
                        row_type
                    ] += f'<td class="{style}">{cell_data[row_type]}</td>'

            for row in row_data.values():
                table_html += row + "</tr>"
            table_html += "<tr></tr>"

    table_html += "</tbody></table></div>"
    return table_html


def get_cell_data(user, day_date, day_str, monthly_presence_data, emp_code):
    cell_data = {
        "status": "A",
        "in_time": "",
        "out_time": "",
        "total_duration": "",
        "leave": "",
        "tour": "",
    }
    if (
        (user.personal_detail.dot and day_date < user.personal_detail.dot)
        or (
            not user.personal_detail.dot
            and user.personal_detail.doj
            and day_date < user.personal_detail.doj
        )
        or (user.personal_detail.dol and day_date >= user.personal_detail.dol)
    ):
        return cell_data

    status_entry = monthly_presence_data.get(emp_code, {}).get(day_str, None)
    if status_entry:
        cell_data.update(
            {
                "status": status_entry.get("present", {}).get(
                    "status", cell_data["status"]
                ),
                "in_time": status_entry.get("present", {}).get("in_time", ""),
                "out_time": status_entry.get("present", {}).get("out_time", ""),
                "total_duration": status_entry.get("present", {}).get(
                    "total_duration", ""
                ),
                "leave": status_entry.get("holiday", {}).get(
                    "status", status_entry.get("leave", {}).get("status", "")
                ),
                "tour": status_entry.get("tour", {}).get("tour", ""),
            }
        )
        if status_entry.get("sunday", {}).get("status"):
            cell_data["status"] = status_entry["sunday"]["status"]
    return cell_data


def get_style(row_type, cell_data):
    if row_type == "status":
        return {
            "P": "text-success",
            "T": "text-primary",
            "A": "text-danger",
            "H": "text-secondary",
        }.get(cell_data[row_type], "text-dark")
    return ""


def generate_monthly_presence_data_detailed(
    converted_from_datetime, converted_to_datetime, is_active, location
):
    monthly_presence_data = defaultdict(lambda: defaultdict(dict))
    employees = (
        User.objects.filter(is_active=is_active)
        .prefetch_related(Prefetch("personal_detail", to_attr="personal_detail_cache"))
        .order_by("first_name")
    )
    if location:
        employees = employees.filter(device_location_id=location).order_by("first_name")

    leaves = LeaveApplication.objects.filter(
        appliedBy__in=employees.values_list("id", flat=True),
        status=settings.APPROVED,
        startDate__range=[converted_from_datetime, converted_to_datetime],
    ).select_related("appliedBy__personal_detail")

    logs = AttendanceLog.objects.filter(
        applied_by__in=employees,
        start_date__range=[converted_from_datetime, converted_to_datetime],
    ).select_related("applied_by__personal_detail")

    all_tours = UserTour.objects.filter(
        applied_by__in=employees,
        status=settings.APPROVED,
        start_date__range=[converted_from_datetime, converted_to_datetime],
    ).select_related("applied_by__personal_detail")

    holidays = get_payroll_date_holidays(converted_from_datetime, converted_to_datetime)
    converted_from_datetime = datetime.strptime(converted_from_datetime, "%Y-%m-%d")
    converted_to_datetime = datetime.strptime(converted_to_datetime, "%Y-%m-%d")

    process_logs(logs, monthly_presence_data)
    process_leaves(leaves, monthly_presence_data)
    process_tours(all_tours, monthly_presence_data)
    process_sundays_and_holidays(
        employees,
        holidays,
        monthly_presence_data,
        converted_from_datetime,
        converted_to_datetime,
    )

    return monthly_presence_data


def process_logs(logs, monthly_presence_data):
    for log in logs:
        emp_code = log.applied_by.personal_detail.employee_code
        log_date = log.start_date
        monthly_presence_data[emp_code][log_date.date().strftime("%Y-%m-%d")][
            "present"
        ] = {
            "status": log.att_status_short_code,
            "in_time": localtime(log.start_date).strftime("%I:%M %p"),
            "out_time": localtime(log.end_date).strftime("%I:%M %p"),
            "total_duration": log.duration,
        }


def process_leaves(leaves, monthly_presence_data):
    for leave in leaves:
        emp_code = leave.appliedBy.personal_detail.employee_code
        current_date = leave.startDate.date()
        end_date = leave.endDate.date()
        while current_date <= end_date:
            leave_type = mark_leave_attendance(
                current_date, leave, current_date.strftime("%Y-%m-%d")
            )
            monthly_presence_data[emp_code][current_date.strftime("%Y-%m-%d")][
                "leave"
            ] = {
                "leave": leave_type,
                "in_time": None,
                "out_time": None,
                "total_duration": None,
            }
            current_date += timedelta(days=1)
from datetime import datetime, timedelta

def process_tours(all_tours, monthly_presence_data):
    for tour in all_tours:
        daily_durations = calculate_daily_tour_durations(tour.start_date, tour.start_time, tour.end_date, tour.end_time)
        
        emp_code = tour.applied_by.personal_detail.employee_code
        for date, short_code, duration in daily_durations:
            monthly_presence_data[emp_code][date.strftime("%Y-%m-%d")]["tour"] = {
                "tour": short_code,
                "in_time": None,
                "out_time": None,
                "total_duration": str(duration),
            }

def calculate_daily_tour_durations(start_date, start_time, end_date, end_time):
    # Combine date and time into datetime objects
    start_datetime = datetime.combine(start_date, start_time or datetime.min.time())
    end_datetime = datetime.combine(end_date, end_time or datetime.min.time())
    
    # Initialize the current datetime to the start datetime
    current_datetime = start_datetime
    daily_durations = []

    while current_datetime.date() <= end_datetime.date():
        # Calculate the end of the current day
        end_of_day = datetime.combine(current_datetime.date(), datetime.max.time())
        
        # Determine the actual end time for the current day
        actual_end_time = min(end_of_day, end_datetime)
        
        # Calculate the duration for the current day
        duration = actual_end_time - current_datetime
        duration_hours = duration.total_seconds() / 3600
        
        # Determine the short code based on duration
        short_code = "T" if duration_hours >= 8 else "TH"
        
        # Append the result for the current day
        daily_durations.append((current_datetime.date(), short_code, duration))
        
        # Move to the next day
        current_datetime = datetime.combine(current_datetime.date() + timedelta(days=1), datetime.min.time())
    
    return daily_durations


def process_sundays_and_holidays(
    employees,
    holidays,
    monthly_presence_data,
    converted_from_datetime,
    converted_to_datetime,
):
    sundays = {
        (converted_from_datetime + timedelta(days=day)).date().strftime("%Y-%m-%d")
        for day in range((converted_to_datetime - converted_from_datetime).days + 1)
        if (converted_from_datetime + timedelta(days=day)).weekday() == 6
    }
    for employee in employees:
        emp_code = employee.personal_detail_cache.employee_code
        for sunday in sundays:
            if sunday not in monthly_presence_data[emp_code]:
                monthly_presence_data[emp_code][sunday]["sunday"] = {
                    "status": "OFF",
                    "in_time": None,
                    "out_time": None,
                    "total_duration": None,
                }
        for holiday in holidays:
            holiday_date = holiday.start_date.strftime("%Y-%m-%d")
            if holiday_date not in monthly_presence_data[emp_code]:
                monthly_presence_data[emp_code][holiday_date]["holiday"] = {
                    "status": holiday.short_code,
                    "in_time": None,
                    "out_time": None,
                    "total_duration": None,
                }


def get_payroll_date_holidays(start_date, end_date):
    holidays = Holiday.objects.filter(start_date__range=[start_date, end_date])
    return list(holidays)


def mark_leave_attendance(current_date, att, day_entry_start):
    if current_date == att.startDate:
        if att.endDayChoice == "1":
            return att.leave_type.leave_type_short_code

        elif att.endDayChoice == "3":
            return f"{att.leave_type.half_day_short_code}"

        elif att.endDayChoice == "2":
            return f"{att.leave_type.half_day_short_code}"

    elif current_date == att.endDate:
        if att.endDayChoice == "2":
            return f"{att.leave_type.half_day_short_code}"
        else:
            if day_entry_start == current_date:
                return "P|L"
            else:
                return att.leave_type.leave_type_short_code
    else:
        return att.leave_type.leave_type_short_code


def format_duration(total_duration):
    hours = int(total_duration)
    minutes = int((total_duration - hours) * 60)
    return f"{hours}:{minutes}"


def format_emp_code(emp_code):
    length = len(emp_code)
    if length == 1:
        return f"00{emp_code}"
    elif length == 2:
        return f"0{emp_code}"
    else:
        return emp_code
