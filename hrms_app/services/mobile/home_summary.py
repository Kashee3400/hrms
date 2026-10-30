"""
Everything on the mobile Home screen except today's live punches
(``GET /api/v1/home/summary/``). Database only, so it stays fast.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from hrms_app.models import (
    AttendanceLog,
    CompensatoryOff,
    Holiday,
    Notification,
    UserTour,
)
from hrms_app.services.leave_approval import is_leave_reviewer, review_queue
from hrms_app.services.leave_balance_summary import get_dashboard_leave_balances
from hrms_app.services.mobile import attendance_codes
from hrms_app.services.mobile.formatters import hhmm, iso_date, shift_payload
from hrms_app.services.mobile.recent_activity import get_recent_activity
from hrms_app.utility.leave_utils import get_employee_requested_tour

ACTIVE_TOUR_STATUSES = [
    settings.PENDING,
    settings.APPROVED,
    settings.EXTENDED,
    settings.PENDING_CANCELLATION,
]


def leave_balances_payload(user):
    seen = set()
    items = []
    for row in get_dashboard_leave_balances(user):
        leave_type = row["leave_type"]
        if leave_type.pk in seen:  # ML can be listed twice by the shared logic
            continue
        seen.add(leave_type.pk)
        items.append(
            {
                "leave_type_id": leave_type.pk,
                "name": leave_type.leave_type,
                "code": leave_type.leave_type_short_code,
                "color": row["color"] or leave_type.color_hex,
                "available": row["total_balance"],
                "balance": row["balance"],
                "on_hold": row["on_hold"],
                "used": row["used_leave"],
                "is_active": row["is_active"],
            }
        )
    return items


def comp_off_payload(user, today):
    open_offs = CompensatoryOff.objects.filter(
        user=user, status=settings.OPEN, expiry_date__gte=today
    ).order_by("expiry_date")
    first = open_offs.first()
    return {
        "available": open_offs.count(),
        "next_expiry": iso_date(first.expiry_date) if first else None,
        "expiring_on_next": (
            open_offs.filter(expiry_date=first.expiry_date).count() if first else 0
        ),
    }


def _tour_payload(tour):
    return {
        "id": tour.pk,
        "slug": tour.slug,
        "from_destination": tour.from_destination,
        "to_destination": tour.to_destination,
        "start_date": iso_date(tour.start_date),
        "start_time": hhmm(tour.start_time),
        "end_date": iso_date(tour.end_date),
        "end_time": hhmm(tour.end_time),
        "extended_end_date": iso_date(tour.extended_end_date),
        "extended_end_time": hhmm(tour.extended_end_time),
        "status": tour.status,
        "status_display": tour.get_status_display(),
        "approval_type": tour.approval_type,
        "approval_type_display": tour.get_approval_type_display(),
        "remarks": tour.remarks,
        "bills_submitted": tour.bills_submitted,
    }


def _active_tour(user, today):
    """Ongoing or next upcoming tour (extended end dates count)."""
    tour = (
        UserTour.objects.filter(applied_by=user, status__in=ACTIVE_TOUR_STATUSES)
        .filter(Q(end_date__gte=today) | Q(extended_end_date__gte=today))
        .order_by("start_date", "start_time")
        .first()
    )
    return _tour_payload(tour) if tour else None


def _month_summary(user, today):
    """Counts from the first of the month up to yesterday (today's log is
    created later), using the same day codes as the Attendance calendar."""
    month_start = today.replace(day=1)
    yesterday = today - timedelta(days=1)
    counts = dict.fromkeys(attendance_codes.CATEGORIES, 0)
    if yesterday >= month_start:
        codes = attendance_codes.day_codes(user, month_start, yesterday, today=today)
        counts = attendance_codes.summarize(codes, attendance_codes.LeaveCodes.load(), yesterday)

    counts.update(attendance_codes.flag_counts(user, month_start, today))
    counts.update(
        {
            "from": month_start.isoformat(),
            "to": yesterday.isoformat() if yesterday >= month_start else None,
        }
    )
    return counts


def _missing_punches(user, today):
    logs = AttendanceLog.objects.filter(
        applied_by=user,
        reg_status=settings.MIS_PUNCHING,
        start_date__date__range=[today.replace(day=1), today],
    ).order_by("-start_date")
    return [
        {
            "date": timezone.localtime(log.start_date).date().isoformat(),
            "first_in": timezone.localtime(log.start_date).isoformat(),
        }
        for log in logs
    ]


def _next_holiday(user, today):
    holiday = (
        Holiday.objects.filter(start_date__gte=today)
        .filter(Q(applicable_users__isnull=True) | Q(applicable_users=user))
        .distinct()
        .order_by("start_date")
        .first()
    )
    if not holiday:
        return None
    return {
        "title": holiday.title,
        "short_code": holiday.short_code,
        "start_date": iso_date(holiday.start_date),
        "end_date": iso_date(holiday.end_date),
        "color": holiday.color_hex,
    }


def _team_pending(user):
    """Only for reviewers (have employees / admin dept / superuser).
    Same queues as the web tracker: leaves incl. cancellation requests,
    tours incl. extensions."""
    if not is_leave_reviewer(user):
        return None
    return {
        "leaves": review_queue(user).count(),
        "tours": get_employee_requested_tour(user).count(),
    }


def get_home_summary(user):
    today = timezone.localdate()
    return {
        "date": today.isoformat(),
        "shift": shift_payload(user),
        "leave_balance_year": today.year,
        "leave_balances": leave_balances_payload(user),
        "comp_off": comp_off_payload(user, today),
        "active_tour": _active_tour(user, today),
        "month_summary": _month_summary(user, today),
        "missing_punches": _missing_punches(user, today),
        "next_holiday": _next_holiday(user, today),
        "team_pending": _team_pending(user),
        "recent_activity": get_recent_activity(user, today),
        "unread_notifications": Notification.objects.filter(receiver=user, is_read=False).count(),
    }
