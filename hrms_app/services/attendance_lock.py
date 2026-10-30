"""
Attendance lock (payroll/audit freeze) for the mobile API.

The database guard stays the web's: pre_save / pre_delete signals call
hrms.utils.check_lock_status(start date) for LeaveApplication, UserTour and
AttendanceLog. This module lets the API refuse *before* that point, with a
clear message, and hide actions on locked records. It is deliberately a bit
stricter than the signal:

- the whole date range counts, not only the start date (a leave from
  28 Sep to 2 Oct touches a locked October);
- locks entered with only lock_month / lock_year also count.
"""
from datetime import date, datetime

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from hrms_app.models import LockStatus


def _as_date(value):
    if isinstance(value, datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return value


def _months(start, end):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def active_lock(start, end=None):
    """The newest lock covering any day of [start, end], or None."""
    start = _as_date(start)
    end = _as_date(end) or start
    by_month = Q()
    for year, month in _months(start, end):
        by_month |= Q(lock_year=year, lock_month=month)
    return (
        LockStatus.objects.filter(is_locked="locked")
        .filter(Q(from_date__lte=end, to_date__gte=start) | by_month)
        .order_by("-locked_at")
        .first()
    )


def lock_message(lock):
    """Same wording as the web's check_lock_status."""
    if lock.from_date and lock.to_date:
        period = f"the period from {lock.from_date} to {lock.to_date}"
    elif lock.lock_month and lock.lock_year:
        period = f"{date(lock.lock_year, lock.lock_month, 1):%B %Y}"
    else:
        period = "this period"
    return f"Action is locked for {period}. Reason: {lock.reason or 'No reason provided'}"


def lock_info(start, end=None):
    """{"is_locked", "reason"} for API payloads."""
    lock = active_lock(start, end)
    return {"is_locked": lock is not None, "lock_reason": lock_message(lock) if lock else None}


def ensure_unlocked(start, end=None):
    """Raises PermissionDenied (DRF answers 403 with the message) when locked."""
    lock = active_lock(start, end)
    if lock:
        raise PermissionDenied(lock_message(lock))
