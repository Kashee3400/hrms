"""
Superuser marks a day Present: the app's counterpart of "Regularize selected
attendance logs" in the web admin, plus half days and days with no punch.

The Detailed Attendance Report keeps showing what really happened: it reads the
first AttendanceLogHistory row for the in time, out time and status, and "R"
says the day was regularized. So the original must be saved before any change.
"""
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.text import slugify

from hrms_app.models import (
    AttendanceGap,
    AttendanceLog,
    AttendanceLogHistory,
    AttendanceSetting,
    AttendanceStatusColor,
    EmployeeShift,
    LeaveDay,
    Notification,
    ShiftTiming,
)
from hrms_app.services import attendance_lock
from hrms_app.services.mobile.formatters import employee_code_label, hhmm, iso_date

FULL_DAY, FIRST_HALF, SECOND_HALF = "full", "first_half", "second_half"
KIND_LABELS = {
    FULL_DAY: "Full Day Present",
    FIRST_HALF: "Half Day Present (First Half)",
    SECOND_HALF: "Half Day Present (Second Half)",
}
LEAVE_HALVES = {settings.FIRST_HALF: FIRST_HALF, settings.SECOND_HALF: SECOND_HALF}


def _aware(day, moment):
    return timezone.make_aware(datetime.combine(day, moment))


def _shift(user):
    assigned = EmployeeShift.objects.filter(employee=user).select_related("shift_timing").first()
    return assigned.shift_timing if assigned else ShiftTiming.objects.first()


def _log_on(user, day):
    return AttendanceLog.objects.filter(applied_by=user, start_date__date=day).order_by("start_date").first()


def _leave_on(user, day):
    """(leave code, half it covers) of the approved leave that day, or (None, None)."""
    leave_day = (
        LeaveDay.objects.filter(
            leave_application__appliedBy=user,
            leave_application__status=settings.APPROVED,
            date=day,
        )
        .select_related("leave_application__leave_type")
        .first()
    )
    if leave_day is None:
        return None, None
    leave = leave_day.leave_application
    leave_type = leave.leave_type
    if leave_day.is_full_day:
        return leave_type.leave_type_short_code, None
    starts_today = timezone.localtime(leave.startDate).date() == day
    choice = leave.startDayChoice if starts_today else leave.endDayChoice
    return leave_type.half_day_short_code or leave_type.leave_type_short_code, LEAVE_HALVES.get(choice)


def _day_problem(user, day, log, today):
    """Why this day can't be marked at all, or None."""
    if day > today:
        return "A future date can't be marked."
    joined = getattr(getattr(user, "personal_detail", None), "doj", None)
    if joined and day < joined:
        return "This date is before the employee joined."
    # Tonight's sync would create this log itself and clash with ours.
    if log is None and day == today:
        return "No punch yet today. A day with no punch can be marked from tomorrow."
    lock = attendance_lock.active_lock(day)
    return attendance_lock.lock_message(lock) if lock else None


def _kind_problem(kind, leave_code, leave_half):
    """Why this choice doesn't fit the day's leave, or None."""
    if leave_code is None:
        return None
    if leave_half is None or kind == FULL_DAY:
        return f"{leave_code} is approved on this day."
    if kind == leave_half:
        half = "first" if leave_half == FIRST_HALF else "second"
        return f"{leave_code} already covers the {half} half."
    return None


def get_day(user, day, today=None):
    """What the superuser needs to see before deciding."""
    today = today or timezone.localdate()
    log = _log_on(user, day)
    leave_code, leave_half = _leave_on(user, day)
    problem = _day_problem(user, day, log, today)
    punch = None
    if log and not log.regularized_backend:
        punch = {
            "first_in": timezone.localtime(log.start_date).isoformat(),
            "last_out": timezone.localtime(log.end_date).isoformat() if log.end_date != log.start_date else None,
            "worked": hhmm(log.duration),
        }
    return {
        "employee": {
            "id": user.pk,
            "name": user.get_full_name() or user.username,
            "code": employee_code_label(user.username),
        },
        "date": iso_date(day),
        "punch": punch,
        "status": log.att_status_short_code if log else None,
        "already_marked": bool(log and log.regularized_backend),
        "leave_code": leave_code,
        "problem": problem,
        "options": [
            {
                "kind": kind,
                "label": label,
                "problem": problem or _kind_problem(kind, leave_code, leave_half),
            }
            for kind, label in KIND_LABELS.items()
        ],
    }


def _original(log):
    """The report's source of truth for this day."""
    if log is None:
        return {
            "start_date": None,
            "end_date": None,
            "from_date": None,
            "to_date": None,
            "duration": None,
            "reg_status": None,
            "att_status_short_code": "A",
        }
    return json.loads(json.dumps(model_to_dict(log), cls=DjangoJSONEncoder))


def _new_times(log, shift, asettings, day, kind):
    full = timedelta(hours=asettings.full_day_hours)
    half = timedelta(hours=asettings.half_day_hours)
    if log is None:
        if kind == FULL_DAY:
            start = _aware(day, shift.start_time)
            return start, start + full
        start = _aware(day, shift.start_time if kind == FIRST_HALF else shift.break_start_time)
        return start, start + half
    if kind == FULL_DAY:
        start = min(log.start_date, _aware(day, shift.grace_start_time))
        return start, max(log.end_date, start + full)
    return log.start_date, max(log.end_date, log.start_date + half)


def _new_log(user, day, start, end):
    title = f"Attendance for {user.get_full_name()} on {day}"
    return AttendanceLog(
        applied_by=user,
        title=title,
        slug=slugify(f"{user.get_full_name()}-{day}"),
        start_date=start,
        end_date=end,
    )


def _tell_employee(user, actor, day, kind):
    Notification.objects.create(
        sender=actor,
        receiver=user,
        message=f"Your attendance for {day:%d %b %Y} was marked {KIND_LABELS[kind]}.",
        notification_type=settings.ATTENDANCE_REGULARISATION,
        target_url="/",
    )


@transaction.atomic
def mark(actor, user, day, kind, reason, today=None):
    """Returns an error message, or None when the day was marked."""
    today = today or timezone.localdate()
    reason = (reason or "").strip()
    if kind not in KIND_LABELS:
        return "Select how to mark this day."
    if not reason:
        return "Please give a reason."

    log = _log_on(user, day)
    leave_code, leave_half = _leave_on(user, day)
    problem = _day_problem(user, day, log, today) or _kind_problem(kind, leave_code, leave_half)
    if problem:
        return problem

    shift = _shift(user)
    asettings = AttendanceSetting.objects.first()
    if shift is None or asettings is None:
        return "Shift timing is not set up."

    original = _original(log)
    start, end = _new_times(log, shift, asettings, day, kind)
    if log is None:
        log = _new_log(user, day, start, end)

    is_full = kind == FULL_DAY
    attendance = settings.PRESENT if is_full else settings.HALF_DAY
    color = AttendanceStatusColor.objects.filter(status=attendance).values_list("color_hex", flat=True).first()

    log.start_date = start
    log.end_date = end
    log.duration = (datetime.min + (end - start)).time()
    log.att_status = attendance
    log.att_status_short_code = "P" if is_full else "H"
    log.color_hex = color
    log.reg_status = None
    log.is_regularisation = False
    log.from_date = log.to_date = None
    log.reg_duration = None
    log.status = None
    log.reason = reason[:100]
    log.regularized = log.is_submitted = log.regularized_backend = True
    log.updated_by = actor
    log.save()

    AttendanceLogHistory.objects.create(attendance_log=log, previous_data=original, modified_by=actor)
    log.add_action(action=settings.APPROVED, performed_by=actor, comment=f"{KIND_LABELS[kind]}. {reason}")
    AttendanceGap.objects.filter(user=user, date=day, is_open=True).update(is_open=False)
    _tell_employee(user, actor, day, kind)
    return None
