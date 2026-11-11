"""
What else today is for the Home card, next to the biometric punches: an
approved leave (full day or one half), a tour, a holiday or the weekly off.
Short leave is hours inside a working day, so it is returned on its own and
shown within the attendance card rather than as an event.

Each event carries its time window so the app can order them and open on the
one happening now (first half present, second half on leave...).
"""
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from hrms_app.models import LeaveApplication, OfficeClosure, UserTour
from hrms_app.services.mobile.attendance_codes import applicable_holidays
from hrms_app.services.mobile.formatters import hhmm

LEAVE_STATUSES = [settings.APPROVED, settings.PENDING_CANCELLATION]
TOUR_STATUSES = [settings.APPROVED, settings.EXTENDED, settings.PENDING_CANCELLATION, settings.COMPLETED]
DAY_START, DAY_END = time(0, 0), time(23, 59)
DEFAULT_SHIFT = (time(9, 30), time(13, 30), time(17, 30))


def _shift_times(user):
    """(start, half-day split, end). The split is the lunch break: the
    first half ends and the second half starts there."""
    assigned = user.shifts.select_related("shift_timing").last()
    shift = assigned.shift_timing if assigned else None
    if shift is None:
        return DEFAULT_SHIFT
    split = shift.break_start_time
    if split is None:
        split = (datetime.combine(datetime.min, shift.start_time) + timedelta(hours=4)).time()
    return shift.start_time, split, shift.end_time


def _window(start, end):
    return {"from": hhmm(start), "to": hhmm(end)}


def _leave_part(leave, today):
    """"full", "first_half" or "second_half" for the part of ``leave`` on ``today``."""
    start = timezone.localtime(leave.startDate).date()
    end = timezone.localtime(leave.endDate).date()
    choice = leave.startDayChoice if today == start else leave.endDayChoice if today == end else settings.FULL_DAY
    return {settings.FIRST_HALF: "first_half", settings.SECOND_HALF: "second_half"}.get(choice, "full")


def _leave_events(user, today, shift):
    start, split, end = shift
    windows = {"full": (start, end), "first_half": (start, split), "second_half": (split, end)}
    leaves = (
        LeaveApplication.objects.filter(
            appliedBy=user,
            status__in=LEAVE_STATUSES,
            startDate__date__lte=today,
            endDate__date__gte=today,
        )
        .select_related("leave_type")
        .order_by("startDate")
    )
    events, short_leave = [], None
    for leave in leaves:
        leave_type = leave.leave_type
        if leave.is_short_leave():
            duration = leave.get_short_leave_duration()
            minutes = int(duration.total_seconds()) // 60 if duration else 0
            short_leave = {
                "id": leave.pk,
                **_window(leave.from_time, leave.to_time),
                "duration": f"{minutes // 60:02}:{minutes % 60:02}",
            }
            continue
        part = _leave_part(leave, today)
        events.append(
            {
                "kind": "leave",
                "id": leave.pk,
                "part": part,
                **_window(*windows[part]),
                "title": leave_type.leave_type,
                "code": leave_type.leave_type_short_code,
                "color": leave_type.color_hex,
                "reference": leave.applicationNo,
                "status": leave.status,
            }
        )
    return events, short_leave


def _tour_events(user, today):
    tours = (
        UserTour.objects.filter(applied_by=user, status__in=TOUR_STATUSES, start_date__lte=today)
        .filter(Q(end_date__gte=today) | Q(extended_end_date__gte=today))
        .order_by("start_date", "start_time")
    )
    events = []
    for tour in tours:
        last_day = tour.extended_end_date or tour.end_date
        last_time = tour.extended_end_time or tour.end_time
        starts = tour.start_time if tour.start_date == today and tour.start_time else DAY_START
        ends = last_time if last_day == today and last_time else DAY_END
        events.append(
            {
                "kind": "tour",
                "id": tour.pk,
                "part": "full" if (starts, ends) == (DAY_START, DAY_END) else "partial",
                **_window(starts, ends),
                "title": f"{tour.from_destination} → {tour.to_destination}",
                "code": "T",
                "color": None,
                "reference": f"{tour.start_date:%d %b} – {last_day:%d %b}",
                "status": tour.status,
            }
        )
    return events


def _day_off_events(user, today, shift):
    start, _, end = shift
    events = [
        {
            "kind": "holiday",
            "id": holiday.pk,
            "part": "full",
            **_window(start, end),
            "title": holiday.title,
            "code": holiday.short_code or "FL",
            "color": holiday.color_hex,
            "reference": None,
            "status": None,
        }
        for holiday in applicable_holidays(user, today, today)
    ]
    closure = OfficeClosure.objects.filter(date=today).first()
    if closure:
        events.append(
            {
                "kind": "holiday",
                "id": closure.pk,
                "part": "full",
                **_window(start, end),
                "title": getattr(closure, "reason", None) or "Office closed",
                "code": closure.short_code or "OC",
                "color": None,
                "reference": None,
                "status": None,
            }
        )
    if not events and today.weekday() == 6:
        events.append(
            {
                "kind": "off",
                "id": None,
                "part": "full",
                **_window(start, end),
                "title": "Weekly off",
                "code": "OFF",
                "color": None,
                "reference": None,
                "status": None,
            }
        )
    return events


def get_today_events(user, today):
    """({"events": [...ordered by start], "short_leave": {...} or None})."""
    shift = _shift_times(user)
    leave_events, short_leave = _leave_events(user, today, shift)
    events = _day_off_events(user, today, shift) + leave_events + _tour_events(user, today)
    events.sort(key=lambda event: event["from"] or "")
    return {"events": events, "short_leave": short_leave}
