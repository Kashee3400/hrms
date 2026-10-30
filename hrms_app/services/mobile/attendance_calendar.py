"""
Month calendar for the mobile Attendance tab
(`GET /api/v1/attendance/calendar/?year=&month=`).

Every day gets ONE final code from the web's AttendanceMapper (see
attendance_codes.day_codes) plus what happened that day - the same sources
as the web calendar (views.EventListView): attendance log, leaves, tours,
holidays and office closures.
"""
import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Max, Q
from django.utils import timezone

from hrms_app.models import AttendanceLog, LeaveApplication, LeaveDay, LockStatus, OfficeClosure, UserTour
from hrms_app.services.mobile import attendance_codes as codes_mod
from hrms_app.services.mobile.formatters import hhmm

HIDDEN_STATUSES = [settings.REJECTED, settings.CANCELLED]

_FLAGS = {
    settings.MIS_PUNCHING: "missing_punch",
    settings.LATE_COMING: "late",
    settings.EARLY_GOING: "early",
}


def _month_bounds(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _days(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _punches(user, start, end):
    """{date: punch dict} from AttendanceLog (one log per day)."""
    result = {}
    logs = AttendanceLog.objects.filter(applied_by=user, start_date__date__range=[start, end]).order_by("start_date")
    for log in logs:
        first_in = timezone.localtime(log.start_date)
        last_out = timezone.localtime(log.end_date) if log.end_date else None
        result[first_in.date()] = {
            "first_in": first_in.isoformat(),
            # A mis-punch log has no real out-time (end == start).
            "last_out": last_out.isoformat() if last_out and last_out != first_in else None,
            "worked": hhmm(log.duration),
            "status": log.att_status,
            "flag": _FLAGS.get(log.reg_status),
        }
    return result


def _leave_events(user, start, end):
    events = defaultdict(list)
    leaves = (
        LeaveApplication.objects.filter(appliedBy=user, startDate__date__lte=end, endDate__date__gte=start)
        .exclude(status__in=HIDDEN_STATUSES)
        .select_related("leave_type")
    )
    half_days = {
        (d.leave_application_id, d.date): d.is_full_day
        for d in LeaveDay.objects.filter(leave_application__in=leaves, date__range=[start, end])
    }
    for leave in leaves:
        first = max(timezone.localtime(leave.startDate).date(), start)
        last = min(timezone.localtime(leave.endDate).date(), end)
        short_leave = leave.is_short_leave() and leave.from_time and leave.to_time
        for day in _days(first, last):
            full = half_days.get((leave.pk, day), True)
            events[day].append(
                {
                    "kind": "leave",
                    "id": leave.pk,
                    "title": leave.leave_type.leave_type,
                    "code": leave.leave_type.leave_type_short_code,
                    # Short leave is a few hours, not a day: show its window.
                    "subtitle": (
                        f"{leave.from_time:%I:%M %p} – {leave.to_time:%I:%M %p}"
                        if short_leave
                        else "Full Day" if full else "Half Day"
                    ),
                    "status": leave.status,
                    "color": leave.leave_type.color_hex,
                }
            )
    return events


def _tour_events(user, start, end):
    events = defaultdict(list)
    tours = (
        UserTour.objects.filter(applied_by=user, start_date__lte=end)
        .filter(Q(extended_end_date__gte=start) | Q(extended_end_date__isnull=True, end_date__gte=start))
        .exclude(status__in=HIDDEN_STATUSES)
    )
    for tour in tours:
        tour_end = tour.extended_end_date or tour.end_date
        for day in _days(max(tour.start_date, start), min(tour_end, end)):
            events[day].append(
                {
                    "kind": "tour",
                    "id": tour.pk,
                    "title": f"{tour.from_destination} → {tour.to_destination}",
                    "subtitle": f"{tour.start_date:%d %b} – {tour_end:%d %b}",
                    "status": tour.status,
                    "color": "#06c1c4",
                }
            )
    return events


def _calendar_events(user, start, end):
    """Holidays and office closures, plus labels for their codes."""
    events, labels = defaultdict(list), {}
    for holiday in codes_mod.applicable_holidays(user, start, end):
        labels[holiday.short_code or "FL"] = holiday.title
        for day in _days(max(holiday.start_date, start), min(holiday.end_date or holiday.start_date, end)):
            events[day].append(
                {"kind": "holiday", "id": holiday.pk, "title": holiday.title, "code": holiday.short_code,
                 "subtitle": holiday.desc or "Holiday", "status": None, "color": holiday.color_hex}
            )
    for closure in OfficeClosure.objects.filter(date__range=[start, end]):
        if closure.short_code:
            labels[closure.short_code] = closure.reason or "Office closed"
        events[closure.date].append(
            {"kind": "closure", "id": closure.pk, "title": closure.reason or "Office closed",
             "code": closure.short_code, "subtitle": closure.get_closure_type_display(), "status": None,
             "color": None}
        )
    return events, labels


def _lock(start, end):
    lock = (
        LockStatus.objects.filter(is_locked="locked")
        .filter(
            Q(from_date__lte=end, to_date__gte=start)
            | Q(lock_year=start.year, lock_month=start.month)
        )
        .order_by("-locked_at")
        .first()
    )
    return {"is_locked": lock is not None, "reason": lock.reason if lock else None}


def get_month_calendar(user, year, month):
    start, end = _month_bounds(year, month)
    today = timezone.localdate()
    leave_codes = codes_mod.LeaveCodes.load()
    day_codes = codes_mod.day_codes(user, start, end, today=today)
    punches = _punches(user, start, end)
    leaves, tours = _leave_events(user, start, end), _tour_events(user, start, end)
    others, extra_labels = _calendar_events(user, start, end)

    def label(code):
        if code in codes_mod.FIXED_LABELS:
            return codes_mod.FIXED_LABELS[code]
        if code in leave_codes:
            return leave_codes.labels[code][0]
        return extra_labels.get(code, code)

    days, legend = [], {}
    for day in _days(start, end):
        code, color = day_codes[day]
        if code:
            legend.setdefault(code, {"code": code, "label": label(code), "color": color,
                                     "category": codes_mod.classify(code, leave_codes)})
        days.append(
            {
                "date": day.isoformat(),
                "code": code,
                "color": color,
                "label": label(code) if code else None,
                "category": codes_mod.classify(code, leave_codes) if code else None,
                "is_today": day == today,
                "punch": punches.get(day),
                "events": others[day] + leaves[day] + tours[day],
            }
        )

    counted_until = min(end, today - timedelta(days=1))
    holiday_days = {d for d, (c, _) in day_codes.items() if c and codes_mod.classify(c, leave_codes) == "holiday"}
    last_sync = AttendanceLog.objects.filter(applied_by=user).aggregate(at=Max("updated_at"))["at"]

    return {
        "year": year,
        "month": month,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "working_days": sum(1 for d in _days(start, end) if d.weekday() != 6 and d not in holiday_days),
        "summary": {
            **codes_mod.summarize(day_codes, leave_codes, counted_until),
            **codes_mod.flag_counts(user, start, end),
            "counted_until": counted_until.isoformat() if counted_until >= start else None,
        },
        "lock": _lock(start, end),
        "last_synced_at": timezone.localtime(last_sync).isoformat() if last_sync else None,
        "legend": sorted(legend.values(), key=lambda item: codes_mod.CATEGORIES.index(item["category"])),
        "days": days,
    }
