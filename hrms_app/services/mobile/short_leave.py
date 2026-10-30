"""
Short Leave (STL) for the mobile app - mirrors the web "Apply Short Leave"
page (ShortLeaveApplicationForm + apply_short_leave.html), with its
client-side gates enforced on the server:

- one date; from/to time; min/max duration from the STL leave type
- attendance for that day must be complete and the employee eligible
  (worked >= 8h - max short leave), from get_attendance_summary
- balance is the STL balance of the selected date's month; one short
  leave books 1 (as the web page does)
"""
from datetime import date, datetime, time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import escape, linebreaks

from hrms_app.hrms.leave_forms import ShortLeaveApplicationForm
from hrms_app.models import AttendanceLog, LeaveApplication, LeaveType
from hrms_app.services import attendance_lock
from hrms_app.services.leave_service import LeaveDomainService
from hrms_app.utility.attendanceutils import get_attendance_summary
from hrms_app.utility.leave_utils import ShortLeavePolicyManager

STL_CODE = "STL"
BOOKED_PER_LEAVE = 1
ACTIVE_STATUSES = [settings.PENDING, settings.APPROVED, settings.PENDING_CANCELLATION, settings.RECOMMEND]


def stl_type():
    return LeaveType.objects.filter(leave_type_short_code=STL_CODE).first()


def _parse_time(raw):
    if not raw:
        return None
    try:
        return time.fromisoformat(str(raw))
    except ValueError:
        return None


def parse_input(data):
    """Returns ((day, from_time, to_time), None) or (None, {field: message})."""
    errors = {}
    try:
        day = date.fromisoformat(str(data.get("date", "")))
    except ValueError:
        day = None
        errors["date"] = "Enter a valid date (YYYY-MM-DD)."
    from_time, to_time = _parse_time(data.get("from_time")), _parse_time(data.get("to_time"))
    if data.get("from_time") and from_time is None:
        errors["from_time"] = "Enter a valid time (HH:MM)."
    if data.get("to_time") and to_time is None:
        errors["to_time"] = "Enter a valid time (HH:MM)."
    return (None, errors) if errors else ((day, from_time, to_time), None)


def _local_iso(value):
    """get_attendance_summary returns raw (UTC) isoformat strings."""
    if not value:
        return None
    return timezone.localtime(datetime.fromisoformat(value)).isoformat()


def preview(user, day, from_time=None, to_time=None):
    leave_type = stl_type()
    if leave_type is None:
        return {"errors": ["Short Leave is not configured. Please contact HR."], "can_submit": False}

    summary = get_attendance_summary(user, day, leave_type)
    available = LeaveDomainService.get_remaining_balance(user=user, leave_type=leave_type, target_date=day)
    errors = []
    lock = attendance_lock.active_lock(day)
    if lock:
        errors.append(attendance_lock.lock_message(lock))

    if not summary["attendance_complete"]:
        # The summary only reads late/early/missing logs (is_regularisation),
        # so tell a full day apart from a day with no attendance yet.
        if AttendanceLog.objects.filter(applied_by=user, start_date__date=day).exists():
            errors.append("Your attendance for this day is complete - no short leave is needed.")
        else:
            errors.append("Attendance for this day isn't available yet. Apply once it is synced.")
    elif not summary["eligible"]:
        errors.append(
            f"Not eligible: worked {summary['worked_minutes']} min. Short leave covers at most "
            f"{summary['max_short_leave_minutes']} min of the {summary['required_minutes']} min day."
        )
    if available - BOOKED_PER_LEAVE < 0:
        errors.append("No Short Leave balance left for this month.")
    if LeaveApplication.objects.filter(
        appliedBy=user, leave_type=leave_type, startDate__date=day, status__in=ACTIVE_STATUSES
    ).exists():
        errors.append("You already have a short leave on this date.")

    duration = None
    if from_time and to_time:
        try:
            duration = ShortLeavePolicyManager(
                user=user,
                leave_type=leave_type,
                start_date=timezone.make_aware(datetime.combine(day, time.min)),
                from_time=from_time,
                to_time=to_time,
            ).apply()
        except ValidationError as exc:
            errors.extend(exc.messages)

    return {
        "leave_type_id": leave_type.pk,
        "date": day.isoformat(),
        "from_time": from_time.strftime("%H:%M") if from_time else None,
        "to_time": to_time.strftime("%H:%M") if to_time else None,
        "duration_minutes": duration,
        "min_minutes": leave_type.min_duration,
        "max_minutes": leave_type.max_duration,
        "attendance": {
            "complete": summary["attendance_complete"],
            "eligible": summary["eligible"],
            "worked_minutes": summary["worked_minutes"],
            "required_minutes": summary["required_minutes"],
            "missing_minutes": summary["missing_minutes"],
            "window_start": _local_iso(summary["attendance_start"]),
            "window_end": _local_iso(summary["attendance_end"]),
        },
        "available": available,
        "booked": BOOKED_PER_LEAVE,
        "projected": available - BOOKED_PER_LEAVE,
        "errors": errors,
        "can_submit": not errors and duration is not None,
    }


def submit(user, day, from_time, to_time, *, leave_address, reason):
    """Saves through the web's ShortLeaveApplicationForm. Returns (app, None) or (None, errors)."""
    # Required on the web form (marked *).
    required = {
        "from_time": (from_time, "From Time is required."),
        "to_time": (to_time, "To Time is required."),
        "leave_address": ((leave_address or "").strip(), "Leave Address is required."),
        "reason": ((reason or "").strip(), "Reason is required."),
    }
    missing = {field: [msg] for field, (value, msg) in required.items() if not value}
    if missing:
        return None, missing
    summary = preview(user, day, from_time, to_time)
    if summary["errors"]:
        return None, {"__all__": summary["errors"]}

    reason = (reason or "").strip()
    form = ShortLeaveApplicationForm(
        data={
            "startDate": day.isoformat(),
            "from_time": from_time.strftime("%H:%M"),
            "to_time": to_time.strftime("%H:%M"),
            "leave_address": (leave_address or "").strip(),
            "reason": linebreaks(escape(reason)) if reason else "",
            "usedLeave": BOOKED_PER_LEAVE,
            "balanceLeave": summary["projected"],
        },
        user=user,
    )
    if not form.is_valid():
        return None, {key: [str(m) for m in msgs] for key, msgs in form.errors.items()}

    # Same as ShortLeaveBaseMixin.form_valid.
    application = form.save(commit=False)
    application.leave_type = stl_type()
    application.endDate = application.startDate
    application.appliedBy = user
    application.save()
    return application, None
