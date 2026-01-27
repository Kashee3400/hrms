from datetime import datetime
from hrms_app.models import DeviceInformation
from hrms_app.hrms.utils import call_soap_api
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from hrms_app.models import (
    Holiday,
    AttendanceLog,
    LeaveDay,
    UserTour,
)
from django.db.models import Q
User = get_user_model()
from datetime import datetime, timedelta

def get_check_in_out_times(user):
    # Validate user info
    if not hasattr(user, 'device_location') or not hasattr(user, 'personal_detail'):
        return None, None

    office_location = user.device_location
    emp_detail = getattr(user, 'personal_detail', None)
    emp_code = getattr(emp_detail, 'employee_code', None)

    if not office_location or not emp_code:
        return None, None

    # Get device instance
    device_instance = DeviceInformation.objects.filter(
        device_location=office_location
    ).first()

    if not device_instance:
        return None, None

    # Prepare date range
    today = datetime.now().date()
    from_date = f"{today} 00:01"
    to_date = f"{today} 23:59"

    # Call SOAP API
    result = call_soap_api(
        device_instance=device_instance, from_date=from_date, to_date=to_date
    )

    if not result or emp_code not in result:
        return None, None

    emp_data = result.get(emp_code, {})
    emp_result = emp_data.get(today)

    if not emp_result or not isinstance(emp_result, list):
        return None, None

    # Extract login/logout
    login_time = emp_result[0]
    logout_time = emp_result[-1] if len(emp_result) > 1 else None

    return login_time, logout_time

def get_from_to_datetime():
    """Returns from_datetime (21st of previous month) and to_datetime (20th of current month)."""
    today = datetime.today()
    # Calculate from_datetime: 21st of previous month
    first_of_this_month = today.replace(day=1)
    from_datetime = (first_of_this_month - timedelta(days=1)).replace(day=21)
    # Calculate to_datetime: 20th of current month
    to_datetime = today.replace(day=20)
    return from_datetime, to_datetime

def get_month_start_end():
    today = datetime.today()
    
    # Start of the month is always day 1
    start_date = today.replace(day=1)

    # To get the last day, go to the next month, then subtract a day
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    
    end_date = next_month - timedelta(days=1)

    return start_date, end_date


def get_days_in_month(start_date, end_date):
    return [
        start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)
    ]

def get_payroll_date_holidays(start_date, end_date, user=None):
    """
    Get holidays for a date range, optionally filtered by user
    """
    holidays = Holiday.objects.filter(
        start_date__range=[start_date, end_date]
    )
    
    if user:
        # Get holidays where:
        # 1. applicable_users is empty (applies to all), OR
        # 2. user is in applicable_users
        holidays = holidays.filter(
            Q(applicable_users__isnull=True) | Q(applicable_users=user)
        ).distinct()
    
    return holidays

def get_non_stl_leave_logs(employee_ids, start_date=None, end_date=None):
    return LeaveDay.objects.non_stl_leave_days(
        employee_ids=employee_ids,
        start_date=start_date,
        end_date=end_date,
    )


def get_stl_leave_logs(employee_ids, start_date=None, end_date=None):
    return LeaveDay.objects.stl_leave_days(
        employee_ids=employee_ids,
        start_date=start_date,
        end_date=end_date,
    )

from django.db.models import Q
from datetime import datetime, time, timedelta
from django.utils.timezone import make_aware

def get_attendance_logs(employee_ids, start_date, end_date):
    """
    Optimization:
    1. select_related('applied_by'): avoids N+1 user queries.
    2. Uses datetime range instead of __date to preserve DB index usage.
    3. Expands range by -1 day and +1 day for edge coverage.
    """

    # Normalize to aware datetimes
    if not isinstance(start_date, datetime):
        start_dt = make_aware(datetime.combine(start_date, time.min))
        end_dt = make_aware(datetime.combine(end_date, time.max))
    else:
        start_dt, end_dt = start_date, end_date

    # 🔹 Expand range
    start_dt -= timedelta(days=1)
    end_dt += timedelta(days=1)

    return (
        AttendanceLog.objects
        .filter(
            applied_by_id__in=employee_ids,
            start_date__range=(start_dt, end_dt),
        )
        .select_related("applied_by")
    )


def get_leave_logs(employee_ids, start_date=None, end_date=None):
    """
    Optimization:
    1. select_related: Fetches the LeaveApplication AND the Employee (appliedBy)
       to avoid hitting the DB when you access leave_log.leave_application.appliedBy.
    """
    return LeaveDay.objects.filter(
        leave_application__appliedBy_id__in=employee_ids,
        date__range=[start_date, end_date],
        leave_application__status=settings.APPROVED,
    ).select_related(
        'leave_application', 
        'leave_application__appliedBy'
    )


def get_tour_logs(employee_ids, start_date, end_date):
    """
    Optimization: select_related for the user.
    """
    return UserTour.objects.filter(
        applied_by_id__in=employee_ids,
        start_date__range=[start_date, end_date],
        status=settings.APPROVED,
    ).select_related('applied_by')


def get_holiday_logs(start_date, end_date, employee_ids=None):
    """
    Optimization:
    1. Removed .annotate(Count): This is expensive.
    2. used Q(applicable_users__isnull=True) to find global holidays.
    3. prefetch_related: If you need to check which users are assigned later.
    """
    # Base filter for date
    base_query = Q(start_date__range=[start_date, end_date])

    if employee_ids:
        # Holidays that are Global (no assigned users) OR assigned to these specific employees
        user_query = Q(applicable_users__isnull=True) | Q(applicable_users__id__in=employee_ids)
        qs = Holiday.objects.filter(base_query & user_query)
    else:
        qs = Holiday.objects.filter(base_query)

    # Distinct is needed because an employee might match multiple groups if you have groups logic,
    # or the join might duplicate rows.
    return qs.distinct().prefetch_related('applicable_users')

# def get_attendance_logs(employee_ids, start_date, end_date):
#     return AttendanceLog.objects.filter(
#         applied_by_id__in=employee_ids, start_date__date__range=[start_date, end_date]
#     )


# def get_leave_logs(employee_ids, start_date=None, end_date=None):
#     return LeaveDay.objects.filter(
#         leave_application__appliedBy_id__in=employee_ids,
#         date__range=[start_date, end_date],
#         leave_application__status=settings.APPROVED,
#     )


# def get_tour_logs(employee_ids, start_date, end_date):
#     return UserTour.objects.filter(
#         applied_by_id__in=employee_ids,
#         start_date__range=[start_date, end_date],
#         status=settings.APPROVED,
#     )


def str_to_date(value):
    from django.utils.timezone import make_aware, utc
    date_time = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    date_time = (
        make_aware(date_time, timezone=utc) if date_time.tzinfo is None else date_time
    )
    return date_time

from django.utils import timezone

def get_worked_minutes(user, date):
    """
    Calculate total worked minutes for a user on a given date
    based on AttendanceLog.
    """

    day_start = timezone.make_aware(
        timezone.datetime.combine(date, timezone.datetime.min.time())
    )
    day_end = timezone.make_aware(
        timezone.datetime.combine(date, timezone.datetime.max.time())
    )

    logs = AttendanceLog.objects.filter(
        applied_by=user,
        start_date__gte=day_start,
        end_date__lte=day_end,
        is_regularisation=True,
    ).exclude(
        reg_status=settings.MIS_PUNCHING
    )

    total_minutes = 0

    for log in logs:
        start = log.start_date
        end = log.end_date

        if timezone.is_aware(start) and timezone.is_aware(end):
            diff = end - start
        else:
            diff = timezone.make_aware(end) - timezone.make_aware(start)

        total_minutes += int(diff.total_seconds() / 60)

    return total_minutes

REQUIRED_DAILY_MINUTES = 8 * 60


def get_attendance_summary(user, date, leave_type):
    """
    Attendance summary assuming ONE attendance row per date.
    """

    log = AttendanceLog.objects.filter(
        applied_by=user,
        start_date__date=date,
        is_regularisation=True
    ).first()

    # -----------------------------
    # Default values (safe)
    # -----------------------------
    worked_minutes = 0
    eligible = False
    attendance_start = None
    attendance_end = None

    if log and log.start_date and log.end_date:
        diff = log.end_date - log.start_date
        worked_minutes = max(0, int(diff.total_seconds() / 60))

        # 🔹 Pass times to frontend
        attendance_start = log.start_date.isoformat()
        attendance_end = log.end_date.isoformat()

    max_slt = int(leave_type.max_duration or 0)

    missing_minutes = max(0, REQUIRED_DAILY_MINUTES - worked_minutes)
    suggested = min(missing_minutes, max_slt)

    # Eligibility rule:
    # worked_minutes >= (8 hrs - max_slt)
    eligible = worked_minutes >= (REQUIRED_DAILY_MINUTES - max_slt)

    return {
        "worked_minutes": worked_minutes,
        "required_minutes": REQUIRED_DAILY_MINUTES,
        "missing_minutes": missing_minutes,
        "max_short_leave_minutes": max_slt,
        "suggested_short_leave_minutes": suggested,
        "eligible": eligible,
        "attendance_complete": bool(log and log.start_date and log.end_date),

        # 🔹 NEW (Frontend use)
        "attendance_start": attendance_start,
        "attendance_end": attendance_end,
    }
