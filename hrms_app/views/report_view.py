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
from hrms_app.utility import attendanceutils as at

class MonthAttendanceReportView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/reports/present_absent_report.html"
    permission_denied_message = _("U are not authorized to access the page")
    title = _("Attendance Report")


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
            employee_ids = employees.values_list("id",flat=True)
            attendance_logs = at.get_attendance_logs(
                employee_ids, converted_from_datetime, converted_to_datetime
            )
            leave_logs = at.get_leave_logs(
                employee_ids, converted_from_datetime, converted_to_datetime
            )
            tour_logs = at.get_tour_logs(
                employee_ids, converted_from_datetime, converted_to_datetime
            )
            holidays = at.get_holiday_logs(
                converted_from_datetime, converted_to_datetime
            )

            attendance_data = at.map_attendance_data(
                attendance_logs=attendance_logs,
                leave_logs=leave_logs,
                holidays=holidays,
                tour_logs=tour_logs,
                start_date_object=converted_from_datetime,
                end_date_object=converted_to_datetime,
            )

            context["days_in_month"] = at.get_days_in_month(
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

from django.core.cache import cache

class LeaveBalanceReportView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/reports/leave_balance_report.html"
    permission_denied_message = _("You are not authorized to access this page.")
    title = _("Leave Balance Report")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date = timezone.now()
        form = LeaveReportFilterForm(self.request.GET)
        if form.is_valid():
            context.update(
                {
                    "table": self._get_filtered_table_data(form_data=form.cleaned_data),
                    "form": form,
                    "search_query" : self.request.GET.get("q", "").strip()
                }
            )
        context.update(
            {
                "date": date,
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

    def _get_filtered_table_data(self, form_data):
        """Generate HTML table data based on form filters."""
        year=form_data.get("year") if form_data.get("year") is not None else now()
        return self.leave_balance_html_table(
            year=year.year
        )

    def leave_balance_html_table(self, year=None):
        year = year or timezone.now().year
        current_month = timezone.now().month
        months = settings.MONTHS
        columns = ["Employee Code", "Employee Name"]
        annual_headers = ["EL", "SL", "CL"]
        monthly_headers = ["EL", "SL", "CL", "LWP", "Closing EL", "Closing SL", "Closing CL"]
        
        cache_key = f"leave_balance_{year}_{current_month}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        table_html = self.generate_table_header(columns, annual_headers, months, monthly_headers,year)
        employees,el_credits = self.get_leave_data(year, monthly_headers)
        table_html += self.generate_table_rows(employees, annual_headers, monthly_headers, el_credits)
        table_html += "</tbody></table></div>"
        
        cache.set(cache_key, table_html, timeout=3600)
        return table_html
    

    def generate_table_header(self, columns, annual_headers, months, monthly_headers, year):
        # Get leave transactions for the given year and extract unique months where EL credits exist
        el_credit_months = set(
            LeaveTransaction.objects.filter(
                transaction_date__year=year,
                leave_balance__leave_type__leave_type_short_code="EL"
            ).values_list("transaction_date__month", flat=True)
        )

        header_html = f"""
        <div class="table-wrapper">
        <table border="1">
        <thead>
            <tr>
                <th>{"</th><th>".join(columns)}</th>
                <th colspan="3">Annual Balance</th>
        """

        # Add month columns with correct colspan
        for i, month in enumerate(months, start=1):
            colspan = len(monthly_headers) + (1 if i in el_credit_months else 0)
            header_html += f'<th colspan="{colspan}">{month}</th>'

        header_html += "</tr><tr><th></th><th></th>"

        # Add annual headers
        header_html += ''.join(f'<th>{header}</th>' for header in annual_headers)

        # Add monthly headers with EL Credit first if exists
        for i, month in enumerate(months, start=1):
            if i in el_credit_months:
                header_html += '<th style="background-color:#FFD700;">EL Credit</th>'  # EL Credit first
            header_html += ''.join(f'<th>{header}</th>' for header in monthly_headers)

        header_html += "</tr></thead><tbody>"

        return header_html

    def get_leave_data(self, year, monthly_headers):
        leave_balance_openings = LeaveBalanceOpenings.objects.filter(
            leave_type__leave_type_short_code__in=["EL", "SL", "CL"],year=year,
        ).values("user_id", "leave_type__leave_type_short_code", "opening_balance", "no_of_leaves")
        leave_opening_dict = defaultdict(lambda: {lt: {"opening_balance": 0, "no_of_leaves": 0} for lt in ["EL", "SL", "CL"]})
        for balance in leave_balance_openings:
            leave_opening_dict[balance["user_id"]][balance["leave_type__leave_type_short_code"]] = {
                "opening_balance": float(balance["opening_balance"] or 0),
                "no_of_leaves": float(balance["opening_balance"] or 0)
            }
        search_query = self.request.GET.get("q", "").strip()
        leave_summary = LeaveApplication.objects.filter(endDate__year=year, status=settings.APPROVED)
        if search_query:
            leave_summary = leave_summary.filter(
                Q(appliedBy__first_name__icontains=search_query) |
                Q(appliedBy__last_name__icontains=search_query) |
                Q(appliedBy__username__icontains=search_query)
            )
        leave_summary = leave_summary.values(
            "endDate__month", "leave_type__leave_type_short_code", "appliedBy__id", "appliedBy__username",
            "appliedBy__first_name", "appliedBy__last_name"
        ).annotate(total_used=Sum("usedLeave"), total_closing=Sum("balanceLeave"))
        el_credit_transactions = LeaveTransaction.objects.filter(
            transaction_date__year=year,
            leave_balance__leave_type__leave_type_short_code="EL"
        ).values("leave_balance__user_id", "transaction_date__month", "no_of_days_approved")
        # Store EL Credit transactions by (user_id, month)
        el_credit_dict = defaultdict(lambda: defaultdict(int))
        for transaction in el_credit_transactions:
            el_credit_dict[transaction["leave_balance__user_id"]][transaction["transaction_date__month"]] = transaction["no_of_days_approved"]

        employees = {}
        for leave in leave_summary:
            emp_id = leave["appliedBy__id"]
            if emp_id not in employees:
                employees[emp_id] = {
                    "emp_code": leave["appliedBy__username"],
                    "emp_name": f"{leave['appliedBy__first_name']} {leave['appliedBy__last_name']}",
                    "annual_balance": leave_opening_dict[emp_id],
                    "monthly_data": {m: {key: 0 for key in monthly_headers} for m in range(1, 13)},
                    "el_credit": el_credit_dict[emp_id],
                }
            month = leave["endDate__month"]
            leave_type = leave["leave_type__leave_type_short_code"]
            employees[emp_id]["monthly_data"][month][leave_type] += leave["total_used"] or 0
            employees[emp_id]["monthly_data"][month][f"Closing {leave_type}"] = (float(leave["total_closing"])) or 0
        return employees, el_credit_dict

    def generate_table_rows(self, employees, annual_headers, monthly_headers, el_credit_dict):
        row_html = ""

        for emp_id, emp in employees.items():
            # Start the row with basic employee info
            row_html += f'<tr><td>{emp["emp_code"]}</td><td>{emp["emp_name"]}</td>'

            # Annual opening balances
            row_html += ''.join(
                f'<td style="background-color:#80008042">{emp["annual_balance"][bal]["opening_balance"]}</td>'
                for bal in annual_headers
            )

            # Initialize opening balance
            opening_balance = {
                key: emp["annual_balance"][key]["no_of_leaves"]
                for key in annual_headers
            }

            for month in range(1, 13):
                # Calculate closing balances
                closing_balance = {
                    key: opening_balance[key] - emp["monthly_data"][month][key]
                    for key in annual_headers
                }

                # ✅ Apply EL credit if available
                if "EL" in annual_headers and month in el_credit_dict.get(emp_id, {}):
                    el_credit = float(el_credit_dict[emp_id][month])
                    closing_balance["EL"] += el_credit
                    # Optional: Display EL credit in a separate column
                    row_html += f'<td style="background-color:#FFD700;">{el_credit}</td>'
                else:
                    el_credit = 0  # still define for consistency

                # Store updated closing balances into monthly_data
                for key in annual_headers:
                    emp["monthly_data"][month][f"Closing {key}"] = round(closing_balance[key], 2)

                # Update opening balance for next month
                opening_balance = closing_balance

                # Add monthly leave usage and closings
                row_html += ''.join(
                    f'<td>{emp["monthly_data"][month][key]}</td>'
                    for key in monthly_headers
                )

            row_html += '</tr>'

        return row_html



    # def generate_table_rows(self, employees, annual_headers, monthly_headers, el_credit_dict):
    #     row_html = ""
    #     for emp_id, emp in employees.items():
    #         row_html += f'<tr><td>{emp["emp_code"]}</td><td>{emp["emp_name"]}</td>'
    #         row_html += ''.join(f'<td style="background-color:#80008042">{emp["annual_balance"][bal]["opening_balance"]}</td>' for bal in annual_headers)

    #         opening_balance = {key: emp["annual_balance"][key]["no_of_leaves"] for key in annual_headers}

    #         for month in range(1, 13):
                
    #             closing_balance = {key: opening_balance[key] - emp["monthly_data"][month][key] for key in annual_headers}
    #             if el_credit_dict[emp_id].get(month,0) > 0:
    #                 closing_balance = float(el_credit_dict[emp_id][month])+closing_balance
    #             for key in annual_headers:
    #                 emp["monthly_data"][month][f"Closing {key}"] = round(closing_balance[key], 2)
    #             opening_balance = closing_balance

    #             row_html += ''.join(f'<td>{emp["monthly_data"][month][key]}</td>' for key in monthly_headers)

    #             # Dynamically add "EL Credit" column **only for months that have EL credit**
    #             if month in el_credit_dict.get(emp_id, {}):
    #                 row_html += f'<td style="background-color:#FFD700;">{el_credit_dict[emp_id][month]}</td>'

    #         row_html += '</tr>'

    #     return row_html
