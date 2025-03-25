from django.contrib.auth import get_user_model
from hrms_app.hrms.form import *
from django.views.generic import (
    TemplateView,
)
from django.db.models.functions import Round
from collections import defaultdict
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
)
from django.utils.translation import gettext_lazy as _
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)
User = get_user_model()
from django.http import HttpResponse
import pandas as pd
from django.utils.timezone import make_aware, localtime, utc
from datetime import datetime, timedelta
from itertools import chain
from hrms_app.utility.report_utils import *


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
        total_days = (end_date_object - start_date_object).days + 1
        sundays = {
            start_date_object + timedelta(days=i)
            for i in range(total_days)
            if (start_date_object + timedelta(days=i)).weekday() == 6
        }

        # Map holidays by date
        holiday_days = {
            holiday.start_date: {
                "status": holiday.short_code,
                "color": holiday.color_hex,
            }
            for holiday in holidays
        }

        # Process attendance logs
        for log in attendance_logs:
            employee_id = log.applied_by.id
            log_date = localtime(log.start_date).date()
            attendance_data[employee_id][log_date] = [
                {
                    "status": log.att_status_short_code,
                    "color": log.color_hex or "#000000",
                }
            ]

        # Process tour logs
        for log in tour_logs:
            daily_durations = calculate_daily_tour_durations(
                log.start_date, log.start_time, log.end_date, log.end_time
            )
            for date, short_code, _ in daily_durations:
                employee_id = log.applied_by.id
                attendance_data[employee_id][date] = [
                    {
                        "status": short_code,
                        "color": "#06c1c4",
                    }
                ]
                holiday_days.pop(date, None)

        # Add holidays to attendance data
        for employee_id, employee_data in attendance_data.items():
            for holiday_date, holiday_info in holiday_days.items():
                employee_data[holiday_date] = [holiday_info]

        # Process leave logs
        for log in leave_logs:
            employee_id = log.leave_application.appliedBy.id
            log_date = log.date
            leave_type = log.leave_application.leave_type
            leave_status = leave_type.leave_type_short_code
            half_status = leave_type.half_day_short_code

            # Handle "CL" leave type
            # Handle "CL" leave type 
            if leave_status == "CL":
                if log_date in holiday_days:
                    # If FL already exists, retain it
                    existing_status = attendance_data[employee_id].get(log_date, [])
                    if any(entry.get("status") == "FL" for entry in existing_status):
                        attendance_data[employee_id][log_date] = existing_status  # Retain FL
                    else:
                        attendance_data[employee_id][log_date] = [
                            {
                                "status": "",
                                "color": holiday_days[log_date]["color"],
                            }
                        ]
                elif log_date.weekday() == 6:  # Sunday
                    # If OFF is already set, retain it
                    existing_status = attendance_data[employee_id].get(log_date, [])
                    if any(entry.get("status") == "OFF" for entry in existing_status):
                        attendance_data[employee_id][log_date] = existing_status  # Retain OFF
                    else:
                        attendance_data[employee_id][log_date] = [
                            {
                                "status": "OFF",
                                "color": "#CCCCCC",
                            }
                        ]
                else:
                    attendance_data[employee_id][log_date] = [
                        {
                            "status": leave_status if log.is_full_day else half_status,
                            "color": leave_type.color_hex or "#FF0000",
                        }
                    ]
            else:
                # Handle other leave types
                if any(
                    entry.get("status") == "FL"
                    for entry in attendance_data[employee_id].get(log_date, [])
                ):
                    attendance_data[employee_id][log_date] = []  # Clear the list

                attendance_data[employee_id][log_date] = [
                    {
                        "status": leave_status if log.is_full_day else half_status,
                        "color": leave_type.color_hex or "#FF0000",
                    }
                ]

        # Add "OFF" status for Sundays without any entries
        for employee_id in attendance_data.keys():
            for sunday in sundays:
                if not attendance_data[employee_id][sunday.date()]:
                    attendance_data[employee_id][sunday.date()] = [
                        {
                            "status": "OFF",
                            "color": "#CCCCCC",  # Default color for "OFF"
                        }
                    ]

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
        context["urls"] = self._get_breadcrumb_urls()

        return context

    def _get_breadcrumb_urls(self):
        """Generate breadcrumb URLs for the template."""
        return [
            ("dashboard", {"label": "Dashboard"}),
            ("attendance_report", {"label": "Attendance Report"}),
        ]

    def _get_date_range(self, from_date, to_date):
        converted_from_datetime = make_aware(datetime.strptime(from_date, "%Y-%m-%d"))
        converted_to_datetime = make_aware(datetime.strptime(to_date, "%Y-%m-%d"))
        return converted_from_datetime, converted_to_datetime

    def _get_holiday_logs(self, start_date, end_date):
        return Holiday.objects.filter(start_date__range=[start_date, end_date])

    def _get_attendance_logs(self, employees, start_date, end_date):
        return AttendanceLog.objects.filter(
            applied_by__in=employees, start_date__date__range=[start_date, end_date]
        )

    def _get_leave_logs(self, employees, start_date, end_date):
        return LeaveDay.objects.filter(
            leave_application__appliedBy__in=employees,
            date__range=[start_date, end_date],
            leave_application__status=settings.APPROVED,
        )

    def _get_tour_logs(self, employees, start_date, end_date):
        return UserTour.objects.filter(
            applied_by__in=employees,
            start_date__range=[start_date, end_date],
            status=settings.APPROVED,
        )
class DetailedMonthlyPresenceView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/reports/present_absent_detailed_report.html"
    permission_denied_message = _("You are not authorized to access this page.")
    title = _("Attendance Detailed Report")

    def get_context_data(self, **kwargs):
        """Prepare context data for rendering the template."""
        context = super().get_context_data(**kwargs)
        form = AttendanceReportFilterForm(self.request.GET)
        if form.is_valid():
            # Get filtered data and generate HTML table
            table_data = self._get_filtered_table_data(form.cleaned_data,self.request.GET.get("q",""))
            context.update(
                {
                    "html_table": table_data,
                    "form": form,
                    "urls": self._get_breadcrumb_urls(),
                    "query":self.request.GET.get("q","")
                }
            )
        else:
            context.update({"form": form, "urls": self._get_breadcrumb_urls()})

        context["title"] = self.title
        return context

    def _get_filtered_table_data(self, form_data,query):
        """Generate HTML table data based on form filters."""
        return get_monthly_presence_html_table(
            converted_from_datetime=form_data.get("from_date"),
            converted_to_datetime=form_data.get("to_date"),
            is_active=form_data.get("active"),
            location=form_data.get("location"),
            query=query,
        )

    def _get_breadcrumb_urls(self):
        """Generate breadcrumb URLs for the template."""
        return [
            ("dashboard", {"label": "Dashboard"}),
            ("detailed_attendance_report", {"label": "Detailed Attendance Report"}),
        ]

    def get(self, request, *args, **kwargs):
        """Handle GET requests, including export functionality."""
        if request.GET.get("export") == "true":
            form = AttendanceReportFilterForm(request.GET)
            if form.is_valid():
                return self._export_table_data(form.cleaned_data)

        return super().get(request, *args, **kwargs)

    def _export_table_data(self, form_data):
        """Export filtered table data to an Excel file."""
        table_data = self._get_filtered_table_data(form_data,self.request.GET.get("q",""))

        # Convert HTML table to DataFrame
        df = pd.read_html(table_data)[0]  # Assuming only one table in HTML content
        filename = f"monthly_presence_data_from_{form_data['from_date']}_to_{form_data['to_date']}.xlsx"

        # Create an Excel writer object
        with pd.ExcelWriter(filename, engine="xlsxwriter") as excel_writer:
            df.to_excel(excel_writer, index=False, sheet_name="Sheet1")

        # Prepare the response with the Excel file
        with open(filename, "rb") as excel_file:
            response = HttpResponse(
                excel_file.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f"attachment; filename={filename}"
            return response

import os

class LeaveBalanceReportView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/reports/leave_balance_report.html"
    permission_denied_message = _("You are not authorized to access this page.")
    title = _("Leave Balance Report")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date = timezone.now()
        table = self.leave_balance_html_table(date.year)
        # month_table= self.monthly_leave_report(date.month),
        form = LeaveReportFilterForm(self.request.GET)
        if form.is_valid():
            context.update(
                {
                    "table": self._get_filtered_table_data(form_data=form.cleaned_data),
                    "form": form,
                }
            )

        context.update(
            {
                "date": date,
                "table": table,
                # "month_table":month_table,
                "urls": self._get_breadcrumb_urls(),
                "form": form,
                "title": self.title,
            }
        )
        return context

    def _get_breadcrumb_urls(self):
        """Generate breadcrumb URLs for the template."""
        return [
            ("dashboard", {"label": "Dashboard"}),
            ("leave_balance_report", {"label": "Leave Balance Report(Yearly)"}),
        ]

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.GET.get("export") == "true":
            form = LeaveReportFilterForm(request.GET)
            if form.is_valid():
                return self._export_table_data(form.cleaned_data)

        return self.render_to_response(context)
    
    def _export_table_data(self, form_data):
        """Export filtered table data to an Excel file."""
        try:
            table_data = self._get_filtered_table_data(form_data)
            # Convert HTML table to DataFrame
            df = pd.read_html(table_data)[0]  # Assuming only one table in HTML content
            # Flatten MultiIndex columns if they exist
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [" ".join(col).strip() for col in df.columns.values]
            # Generate filename
            filename = f"employee_leave_balance_report_{form_data['year']}.xlsx"
            # Create an Excel writer object
            with pd.ExcelWriter(filename, engine="xlsxwriter") as excel_writer:
                df.to_excel(excel_writer, index=False, sheet_name="Leave Balance")
            # Prepare the response with the Excel file
            with open(filename, "rb") as excel_file:
                response = HttpResponse(
                    excel_file.read(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Content-Disposition"] = f"attachment; filename={filename}"
            # Clean up the temporary file
            os.remove(filename)
            return response
        except Exception as e:
            return HttpResponse("An error occurred while exporting the report.", status=500)

    def _get_filtered_table_data(self, form_data):
        """Generate HTML table data based on form filters."""
        year=form_data.get("year") if form_data.get("year") is not None else now().year
        
        return self.leave_balance_html_table(
            year=year
        )

    def _get_filtered_month_table_data(self, form_data):
        """Generate HTML table data based on form filters."""
        return self.monthly_leave_report(
            year=form_data.get("year").year,
            month=form_data.get("year").month,
        )


    def leave_balance_html_table(self, year=None):
        year = year if year else timezone.now().year
        current_month = timezone.now().month  # Get the current month
        months = settings.MONTHS
        columns = ["Employee Code", "Employee Name"]
        annual_headers = ["EL", "SL", "CL"]
        monthly_headers = ["EL", "SL", "CL", "LWP", "Closing EL", "Closing SL", "Closing CL"]

        # HTML Table Header
        table_html = """
        <div class="table-wrapper">
        <table border="1">
        <thead>
            <tr>
                <th>{}</th>
                <th colspan="3">Annual Balance</th>
        """.format("</th>\n<th>".join(columns))

        # Add monthly columns up to the current month
        for month in months[:current_month]:
            table_html += f'    <th colspan="7">{month}</th>\n'

        # Add "EL Credit" column after March
        if current_month >= 3:
            table_html += '    <th style="background-color:#FFD700;">EL Credit</th>\n'

        table_html += "    </tr>\n    <tr>\n<th></th>\n<th></th>\n"

        # Add headers for annual balance and monthly data
        table_html += "".join(f"<th>{header}</th>" for header in annual_headers)
        for month in months[:current_month]:
            table_html += "".join(f"<th>{header}</th>" for header in monthly_headers)

        if current_month >= 3:
            table_html += "    <th></th>\n"  # Empty header for EL Credit

        table_html += "    </tr>\n</thead>\n<tbody>\n"

        # Fetch leave balances
        leave_balance_openings = LeaveBalanceOpenings.objects.filter(
            leave_type__leave_type_short_code__in=["EL", "SL", "CL"]
        ).values(
            "user_id",
            "leave_type__leave_type_short_code",
            "opening_balance",
            "no_of_leaves",
        )

        # Store leave balances in a structured dictionary
        leave_opening_dict = defaultdict(lambda: {"EL": {"opening_balance": 0, "no_of_leaves": 0},
                                                "SL": {"opening_balance": 0, "no_of_leaves": 0},
                                                "CL": {"opening_balance": 0, "no_of_leaves": 0}})
        
        for balance in leave_balance_openings:
            user_id = balance["user_id"]
            leave_type = balance["leave_type__leave_type_short_code"]
            leave_opening_dict[user_id][leave_type] = {
                "opening_balance": float(balance["opening_balance"] or 0),
                "no_of_leaves": float(balance["no_of_leaves"] or 0)
            }

        # Search filter for employees
        search_query = self.request.GET.get("q", "").strip()
        leave_summary = LeaveApplication.objects.filter(endDate__year=year,status=settings.APPROVED)

        if search_query:
            leave_summary = leave_summary.filter(
                Q(appliedBy__first_name__icontains=search_query) |
                Q(appliedBy__last_name__icontains=search_query) |
                Q(appliedBy__username__icontains=search_query)
            )

        # Aggregate leave usage and balance
        leave_summary = (
            leave_summary.values(
                "endDate__month",
                "leave_type__leave_type",
                "appliedBy__id",
                "appliedBy__username",
                "appliedBy__first_name",
                "appliedBy__last_name",
            )
            .annotate(total_used=Sum("usedLeave"), total_closing=Sum("balanceLeave"))
            .order_by("endDate__month")
        )

        employees = {}

        for leave in leave_summary:
            emp_id = leave["appliedBy__id"]
            transaction = LeaveTransaction.objects.filter(
                leave_balance__user_id=emp_id, transaction_date__month=current_month
            ).last()

            if emp_id not in employees:
                employees[emp_id] = {
                    "emp_code": leave["appliedBy__username"],
                    "emp_name": f"{leave['appliedBy__first_name']} {leave['appliedBy__last_name']}",
                    "annual_balance": leave_opening_dict[emp_id],
                    "monthly_data": {m: {key: 0 for key in monthly_headers} for m in range(1, 13)},
                    "el_credit": transaction.no_of_days_approved if transaction is not None else 0,
                }

            month = leave["endDate__month"]
            leave_type = leave["leave_type__leave_type"]
            total_used = leave["total_used"] or 0
            total_closing = leave["total_closing"] or 0

            # Update employee monthly data
            if "EL" in leave_type:
                employees[emp_id]["monthly_data"][month]["EL"] += total_used
                employees[emp_id]["monthly_data"][month]["Closing EL"] = total_closing
            elif "SL" in leave_type:
                employees[emp_id]["monthly_data"][month]["SL"] += total_used
                employees[emp_id]["monthly_data"][month]["Closing SL"] = total_closing
            elif "CL" in leave_type:
                employees[emp_id]["monthly_data"][month]["CL"] += total_used
                employees[emp_id]["monthly_data"][month]["Closing CL"] = total_closing
            else:
                employees[emp_id]["monthly_data"][month]["LWP"] += total_used

        # Generate table rows
        for emp in employees.values():
            table_html += "    <tr>\n"
            table_html += f'        <td>{emp["emp_code"]}</td>\n'
            table_html += f'        <td>{emp["emp_name"]}</td>\n'

            # Annual leave balance
            table_html += "".join(
                f'<td style="background-color:#80008042">{emp["annual_balance"][bal]["opening_balance"]}</td>'
                for bal in ["EL", "SL", "CL"]
            )

            # Initialize opening balance for January
            opening_balance = {key: emp["annual_balance"][key]["no_of_leaves"] for key in ["EL", "SL", "CL"]}

            for month in range(1, 13):
                if month > current_month:
                    continue  # Skip future months

                # Calculate closing balance
                closing_balance = {
                    "EL": opening_balance["EL"] - emp["monthly_data"][month]["EL"],
                    "SL": opening_balance["SL"] - emp["monthly_data"][month]["SL"],
                    "CL": opening_balance["CL"] - emp["monthly_data"][month]["CL"],
                }

                # Update monthly data with closing balance
                emp["monthly_data"][month]["Closing EL"] = round(closing_balance["EL"], 2)
                emp["monthly_data"][month]["Closing SL"] = round(closing_balance["SL"], 2)
                emp["monthly_data"][month]["Closing CL"] = round(closing_balance["CL"], 2)

                # Update opening balance for next month
                opening_balance = closing_balance

                # Add monthly data to the table
                table_html += "".join(
                    f"<td>{emp['monthly_data'][month][key]}</td>"
                    for key in monthly_headers
                )

            # Add "EL Credit" column if applicable
            if current_month >= 3:
                table_html += f'<td style="background-color:#FFD700;">{emp["el_credit"]}</td>\n'

            table_html += "    </tr>\n"

        table_html += "    </tbody>\n</table>\n</div>\n"
        return table_html
