"""Latest leave, tour and attendance events for the mobile Home timeline."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from hrms_app.models import AttendanceLog, LeaveApplication, UserTour

LIMIT = 5
ATTENDANCE_LOOKBACK_DAYS = 14

_FLAG_LABELS = {
    settings.MIS_PUNCHING: ("Missing punch-out", "missing"),
    settings.LATE_COMING: ("Late coming", "late"),
    settings.EARLY_GOING: ("Early going", "early"),
}


def _days(value):
    return f"{value:g} day" + ("" if value == 1 else "s")


def _leave_items(user):
    for leave in (
        LeaveApplication.objects.filter(appliedBy=user)
        .select_related("leave_type")
        .order_by("-updatedAt")[:LIMIT]
    ):
        start = timezone.localtime(leave.startDate).date()
        end = timezone.localtime(leave.endDate).date()
        period = start.strftime("%d %b") if start == end else f"{start:%d %b} – {end:%d %b}"
        yield {
            "kind": "leave",
            "id": leave.pk,
            "title": leave.leave_type.leave_type,
            "subtitle": f"{period} ({_days(leave.usedLeave or 0)})",
            "status": leave.status,
            "status_display": leave.get_status_display(),
            "color": leave.leave_type.color_hex,
            "timestamp": leave.updatedAt,
        }


def _tour_items(user):
    for tour in UserTour.objects.filter(applied_by=user).order_by("-updated_at")[:LIMIT]:
        yield {
            "kind": "tour",
            "id": tour.pk,
            "title": f"Tour: {tour.from_destination} → {tour.to_destination}",
            "subtitle": f"{tour.start_date:%d %b} – {tour.end_date:%d %b}",
            "status": tour.status,
            "status_display": tour.get_status_display(),
            "color": None,
            "timestamp": tour.updated_at,
        }


def _attendance_items(user, today):
    """Only flagged days (late / early / missing punch) are newsworthy."""
    logs = AttendanceLog.objects.filter(
        applied_by=user,
        reg_status__in=list(_FLAG_LABELS),
        start_date__date__gte=today - timedelta(days=ATTENDANCE_LOOKBACK_DAYS),
    ).order_by("-start_date")[:LIMIT]
    for log in logs:
        label, status = _FLAG_LABELS[log.reg_status]
        start = timezone.localtime(log.start_date)
        end = timezone.localtime(log.end_date)
        times = f"In {start:%I:%M %p}" if status == "missing" else f"In {start:%I:%M %p}, Out {end:%I:%M %p}"
        yield {
            "kind": "attendance",
            "id": log.pk,
            "date": start.date().isoformat(),
            "title": f"{start:%d %b} • {label}",
            "subtitle": times,
            "status": status,
            "status_display": "Missing" if status == "missing" else label.split()[0],
            "color": log.color_hex,
            "timestamp": log.start_date,
        }


def get_recent_activity(user, today):
    items = [*_leave_items(user), *_tour_items(user), *_attendance_items(user, today)]
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return [{**item, "timestamp": item["timestamp"].isoformat()} for item in items[:LIMIT]]
