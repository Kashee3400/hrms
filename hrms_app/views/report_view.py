from django.contrib.auth import get_user_model
from itertools import chain
from datetime import timedelta
from django.utils.timezone import make_aware
from django.conf import  settings
from hrms_app.hrms.form import AttendanceReportFilterForm
from django.db.models import Q
from django.utils.html import format_html
from ..models import OfficeLocation,AttendanceLog,UserTour
from hrms_app.hrms.form import *
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
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.timezone import now
from django.contrib.messages.views import SuccessMessageMixin

logger = logging.getLogger(__name__)


class MonthAttendanceReportView(LoginRequiredMixin,TemplateView):
    template_name = "hrms_app/reports/present_absent_report.html"

    def get_context_data(self, **kwargs):
        """Prepare the context for the template."""
        context = super().get_context_data(**kwargs)
        
        # Get the form for employee selection
        form = AttendanceReportFilterForm(self.request.GET)

        # Extract parameters from the GET request (location, from_date, to_date)
        location = self.request.GET.get('location')
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')

        if location and from_date and to_date:
            try:
                converted_from_datetime = make_aware(datetime.strptime(from_date, "%Y-%m-%d"))
                converted_to_datetime = make_aware(datetime.strptime(to_date, "%Y-%m-%d"))
            except ValueError:
                # Handle invalid date format, if needed
                context['error'] = "Invalid date format. Please use YYYY-MM-DD."
                return context
        
            # Generate the attendance report HTML table
            table_html = get_monthly_presence(converted_from_datetime, converted_to_datetime, location)
            
            # Add the attendance table to the context
        else:
            # If no filters are provided, just show a form with no data
            start_date, end_date = get_payroll_start_end_date(now().date)
            table_html = get_monthly_presence(start_date, end_date, location)
            context.update(
                {
                    "form": form,
                    "error": "Please select location and date range.",  # Provide error message
                }
            )
            
        context.update(
                {
                    "current_date": now(),
                    "form": form,
                    "table_html": table_html,  # Include the generated table HTML
                    "urls": [
                        ("dashboard", {"label": "Dashboard"}),
                        ("calendar", {"label": "Attendance Report"}),
                    ],
                }
            )
        return context


def get_monthly_presence(converted_from_datetime, converted_to_datetime, location_name,is_active=True):
    """
    Generates the monthly attendance report for a given location.
    
    :param converted_from_datetime: The start datetime for the report period.
    :param converted_to_datetime: The end datetime for the report period.
    :param location_name: The location name to filter the employees by.
    :return: HTML table containing attendance status for each employee.
    """
    # Fetch the start and end date in the correct format
    start_fetch_date_str = converted_from_datetime.strftime('%Y-%m-%d %H:%M')
    end_fetch_date_str = converted_to_datetime.strftime('%Y-%m-%d %H:%M')
    office_location = OfficeLocation.objects.all()
    
    # Get the location dynamically based on the provided location_name from frontend
    location =  office_location.filter(office_type=location_name) if location_name else  office_location.filter(office_type=settings.HEAD_OFFICE)

    # Fetch the users (dynamic user model) based on location
    User = get_user_model()  # This gets the custom user model dynamically
    
    # Filter users by location and exclude specific emails
    all_objects = User.objects.filter(location=location,is_active=is_active).exclude(
        email__in=['admin@gmail.com']
    )

    # Fetch all attendance logs for the specified period
    attendance_logs = AttendanceLog.objects.filter(
        applied_by__in=all_objects,
        start_date__gte=converted_from_datetime,
        end_date__lte=converted_to_datetime
    )

    # Prepare a list of logs by employee code and date
    attendance_dict = {}
    for log in attendance_logs:
        emp_code = log.applied_by.personal_detail.employee_code
        # Add entry for each log with date keys
        for date in log.date_range():
            if emp_code not in attendance_dict:
                attendance_dict[emp_code] = {}
            status = log.att_status or "A"  # Default to "Absent" if no status
            attendance_dict[emp_code][date.strftime('%Y-%m-%d')] = {
                'status': status,
                'att_status_short_code': log.att_status_short_code,
                'color_hex': log.color_hex
            }

    # Generate table rows for HTML
    table_rows = []
    for emp in all_objects:
        if emp.emp_code in attendance_dict:
            row_data = [f'<td class="sticky-col">KMPCL-{format_emp_code(emp.emp_code)}</td>']
            row_data.append(f'<td class="sticky-col">{emp.first_name} {emp.last_name}</td>')

            # Loop through each day in the date range
            for day in range((converted_to_datetime - converted_from_datetime).days + 1):
                day_date = converted_from_datetime.date() + timedelta(days=day)
                day_str = day_date.strftime('%Y-%m-%d')

                # Determine the status for the current day
                attendance_entry = attendance_dict.get(emp.emp_code, {}).get(day_str)
                status = "A"  # Default to absent
                if attendance_entry:
                    status = attendance_entry['status']

                # Define colors based on the status
                color_class = {
                    "P": "class=\"text-success\"",
                    "A": "class=\"text-danger\"",
                    "OFF": "class=\"text-muted\"",
                    "L": "style=\"color:#9f4eb5;\"",
                    "EL": "style=\"color:#9f4eb5;\"",
                    "SL": "style=\"color:#9f4eb5;\"",
                    "CL": "style=\"color:#9f4eb5;\"",
                    "T": "style=\"color:rgb(0, 195, 204);\"",
                    "FL": "style=\"color:#ffa500;\""
                }.get(status, "text-black")

                # Append the status with its respective color class
                row_data.append(f'<td {color_class}>{status}</td>')

            # Add this row to the table
            table_rows.append(f"<tr>{''.join(row_data)}</tr>")

    # Return the complete table HTML as a string
    table_data = "".join(table_rows)
    return table_data

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
