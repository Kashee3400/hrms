from hrms_app.models import (
    LeaveBalanceOpenings,
    LeaveType,
    LeaveTransaction,
)
from collections import defaultdict
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.db import transaction
import json
from datetime import datetime, timedelta
from django.contrib.admin.models import LogEntry, CHANGE, ADDITION
from django.contrib.contenttypes.models import ContentType
from hrms_app.utility import attendanceutils as at
from django.contrib.auth import get_user_model
from django.utils.timezone import make_aware
from ..utility.attendance_mapper import aggregate_attendance_data

User = get_user_model()


def log_admin_action(user, obj, action_flag, message):
    LogEntry.objects.log_action(
        user_id=user.pk,
        content_type_id=ContentType.objects.get_for_model(obj).pk,
        object_id=obj.pk,
        object_repr=str(obj),
        action_flag=action_flag,
        change_message=message,
    )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(lambda u: u.is_superuser), name="dispatch")
class ForwardLeaveBalanceView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            year = int(data.get("year", timezone.now().year))
            next_year = year + 1

            current_balances = LeaveBalanceOpenings.objects.filter(year=year)

            if not current_balances.exists():
                return JsonResponse(
                    {"detail": f"No leave balances found for year {year}."}, status=404
                )

            new_entries = []
            with transaction.atomic():
                for balance in current_balances:
                    # Update closing balance for current year
                    balance.closing_balance = balance.remaining_leave_balances or 0
                    balance.save()

                    code = balance.leave_type.leave_type_short_code.upper()

                    if code in ["SL", "EL"]:
                        carry_forward = balance.remaining_leave_balances or 0
                    elif code == "CL":
                        carry_forward = 10
                    elif code in ["ML", "LWP"]:
                        carry_forward = 0
                    else:
                        continue  # skip if code is unknown or not handled

                    new_entry = LeaveBalanceOpenings(
                        user=balance.user,
                        leave_type=balance.leave_type,
                        year=next_year,
                        no_of_leaves=carry_forward,
                        remaining_leave_balances=carry_forward,
                        opening_balance=carry_forward,
                        closing_balance=0,
                    )
                    new_entries.append(new_entry)

                # Avoid duplicates
                existing_pairs = LeaveBalanceOpenings.objects.filter(
                    year=next_year
                ).values_list("user_id", "leave_type_id")
                existing_set = set(existing_pairs)

                filtered_new_entries = [
                    entry
                    for entry in new_entries
                    if (entry.user_id, entry.leave_type_id) not in existing_set
                ]

                # Bulk create new entries
                LeaveBalanceOpenings.objects.bulk_create(filtered_new_entries)
                for entry in filtered_new_entries:
                    log_admin_action(
                        request.user,
                        entry,
                        ADDITION,
                        f"Created leave balance for year {entry.year} with code {entry.leave_type.leave_type_short_code}",
                    )

            return JsonResponse(
                {
                    "detail": f"Leave balances forwarded from {year} to {next_year}.",
                    "records_created": len(filtered_new_entries),
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(lambda u: u.is_superuser), name="dispatch")
class CreditELLeaveView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            year = data.get("year", timezone.now().year)
            employee_data = data.get("employees", [])
            emp_codes = [emp["emp_code"] for emp in employee_data]
            emp_credit_map = {emp["emp_code"]: emp["balance"] for emp in employee_data}
            el_type = LeaveType.objects.get(leave_type_short_code="EL")
            balances = LeaveBalanceOpenings.objects.select_related("user").filter(
                leave_type=el_type, year=year, user__username__in=emp_codes
            )
            if not balances.exists():
                return JsonResponse(
                    {"detail": f"No EL leave balances found for year {year}."},
                    status=404,
                )
            updated = 0
            errors = []
            with transaction.atomic():
                transactions = []
                for balance in balances:
                    emp_code = balance.user.username
                    days = emp_credit_map.get(emp_code)
                    if days is None:
                        errors.append(f"{emp_code}: Credit days not provided.")
                        continue
                    try:
                        balance.remaining_leave_balances = (
                            balance.remaining_leave_balances or 0
                        ) + days
                        balance.save()
                        transactions.append(
                            LeaveTransaction(
                                leave_balance=balance,
                                leave_type=el_type,
                                transaction_date=timezone.now(),
                                no_of_days_applied=0,
                                no_of_days_approved=days,
                                transaction_type="add",
                                remarks="Quarterly EL credit",
                            )
                        )

                        log_admin_action(
                            request.user,
                            balance,
                            CHANGE,
                            f"Credited {days} EL for {emp_code} year {year}.",
                        )
                        updated += 1
                    except Exception as e:
                        errors.append(f"{emp_code}: {str(e)}")
                LeaveTransaction.objects.bulk_create(transactions)

            return JsonResponse(
                {
                    "detail": f"{updated} EL credits processed for year {year}.",
                    "errors": errors,
                }
            )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class UserAttendanceAggregation(View):
    def _get_filtered_employees(self, location=None, active=False):
        employees = User.objects.filter(is_active=active)
        # Uncomment and modify the location filter if needed
        # if location:
        #     employees = employees.filter(device_location_id=location)
        return employees.order_by("first_name")

    def _get_date_range(self, from_date, to_date):
        converted_from_datetime = make_aware(datetime.strptime(from_date, "%Y-%m-%d"))
        converted_to_datetime = make_aware(datetime.strptime(to_date, "%Y-%m-%d"))
        return converted_from_datetime, converted_to_datetime

    def get(self, request, *args, **kwargs):
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if not start_date or not end_date:
            return JsonResponse(
                {"error": "Start and end dates are required."}, status=400
            )

        try:
            converted_from_datetime, converted_to_datetime = self._get_date_range(
                start_date, end_date
            )
        except ValueError:
            return JsonResponse(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        employees = self._get_filtered_employees(active=True)
        employee_ids = employees.values_list("id", flat=True)

        attendance_data = aggregate_attendance_data(
            employee_ids=employee_ids,
            start_date_object=converted_from_datetime,
            end_date_object=converted_to_datetime,
        )
        aggregated_status_counts = {}

        for user_id, daily_data in attendance_data.items():
            status_counter = defaultdict(float)

            for day, records in daily_data.items():
                for record in records:
                    status = record.get("status")
                    increment = 0.5 if status in ["H"] else 1
                    status_counter[status] += increment

            # Add total of all statuses
            status_counter["total"] = sum(status_counter.values())
            aggregated_status_counts[user_id] = dict(status_counter)

        return JsonResponse(
            {
                "aggregated_status_counts": aggregated_status_counts,
                "start_date": start_date,
                "end_date": end_date,
                "total_days": (converted_to_datetime - converted_from_datetime).days
                + 1,
            },
            status=200,
        )
