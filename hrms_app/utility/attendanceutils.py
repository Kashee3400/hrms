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

def get_holiday_logs(start_date, end_date, employee_ids=None):
    """
    Get holidays for a date range, optionally filtered by specific employees
    """
    from django.db.models import Count, Q
    
    holidays = Holiday.objects.filter(start_date__range=[start_date, end_date])
    
    if employee_ids:
        # Get holidays where:
        # 1. No users assigned (applies to all), OR
        # 2. At least one of the employees is in applicable_users
        holidays = holidays.annotate(
            user_count=Count('applicable_users')
        ).filter(
            Q(user_count=0) | Q(applicable_users__id__in=employee_ids)
        ).distinct()
    
    return holidays

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


def get_attendance_logs(employee_ids, start_date, end_date):
    return AttendanceLog.objects.filter(
        applied_by_id__in=employee_ids, start_date__date__range=[start_date, end_date]
    )


def get_leave_logs(employee_ids, start_date=None, end_date=None):
    return LeaveDay.objects.filter(
        leave_application__appliedBy_id__in=employee_ids,
        date__range=[start_date, end_date],
        leave_application__status=settings.APPROVED,
    )


def get_tour_logs(employee_ids, start_date, end_date):
    return UserTour.objects.filter(
        applied_by_id__in=employee_ids,
        start_date__range=[start_date, end_date],
        status=settings.APPROVED,
    )


def str_to_date(value):
    from django.utils.timezone import localtime, make_aware, utc
    date_time = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    date_time = (
        make_aware(date_time, timezone=utc) if date_time.tzinfo is None else date_time
    )
    return date_time
