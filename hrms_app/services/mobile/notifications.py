"""
The mobile Notifications screen. Only what the employee received: the sender's
own copy is a different person's message (see services/workflow_messages.py).

Rows store plain text, so the title and kind are read from it. That covers the
older wording too ("... has been pending."). Colours are the ones employees
already know from the calendar: the leave type's, the tour's and Absent's.
"""
from django.conf import settings

from hrms_app.models import AttendanceGap, AttendanceStatusColor, LeaveApplication, Notification, UserTour
from hrms_app.services import tour_approval
from hrms_app.services.mobile.attendance_codes import ABSENT_COLOR, TOUR_COLOR
from hrms_app.services.mobile.my_leaves import PAGE_SIZE
from hrms_app.services.notification_push import (
    APPROVALS_ROUTE,
    APPROVALS_TOURS_ROUTE,
    ATTENDANCE_GAPS_ROUTE,
    app_route,
)

LEAVE, TOUR, ATTENDANCE, OTHER = "leave", "tour", "attendance", "other"
CATEGORIES = {
    settings.LEAVE_STATUS: LEAVE,
    settings.TOUR_STATUS: TOUR,
    settings.ATTENDANCE_REGULARISATION: ATTENDANCE,
}
FILTERS = {
    LEAVE: settings.LEAVE_STATUS,
    TOUR: settings.TOUR_STATUS,
    ATTENDANCE: settings.ATTENDANCE_REGULARISATION,
}
LEAVE_AWAITING = {settings.PENDING, settings.RECOMMEND, settings.PENDING_CANCELLATION}
REVIEW_KINDS = {"review", "schedule", "cancel_request"}
GAP_KINDS = {"reminder", "last_day", "missing_punch", "expired"}


def _attendance_kind(row):
    text = row.message.lower()
    if row.go_route_mobile != ATTENDANCE_GAPS_ROUTE:
        return "info", "Attendance Update"
    if "not updated in time" in text:
        return "team_gap", "Attendance Not Updated"
    if "last day" in text:
        return "last_day", "Last Day Today"
    if "has ended" in text:
        return "expired", "Time to Apply Is Over"
    if "missing" in text:
        return "missing_punch", "Missing Punch-out"
    return "reminder", "Update Your Attendance"


def _workflow_kind(text, noun, is_reviewer):
    """(kind, title) of a leave or tour message."""
    if "changed the schedule" in text:
        return "schedule", "Tour Schedule Changed"
    if "your updated" in text:
        return "submitted", "Tour Sent Again"
    if "pending_cancellation" in text or "pending cancellation" in text or "requested to cancel" in text:
        return "cancel_request", "Cancellation Request"
    if "cancellation request" in text:
        return "cancel_sent", "Cancellation Requested"
    if "please approve or reject" in text:
        return "review", "LWP Waiting for Decision"
    if "please review" in text:
        return "review", "Review Needed"
    if "not recommended" in text or "did not recommend" in text:
        return "rejected", f"{noun} Not Recommended"
    if "recommended" in text:
        return "recommended", f"{noun} Recommended"
    for word, kind in (
        ("rejected", "rejected"),
        ("cancelled", "cancelled"),
        ("approved", "approved"),
        ("extended", "extended"),
        ("completed", "approved"),
    ):
        if word in text:
            return kind, f"{noun} {word.title()}"
    if "pending" in text or "submitted" in text:
        return ("review", "Review Needed") if is_reviewer else ("submitted", f"{noun} Submitted")
    return "info", f"{noun} Update"


def _load_related(rows):
    def ids(notification_type):
        return [
            row.related_object_id
            for row in rows
            if row.notification_type == notification_type and row.related_object_id
        ]

    leaves = LeaveApplication.objects.select_related("leave_type").in_bulk(ids(settings.LEAVE_STATUS))
    tours = UserTour.objects.in_bulk(ids(settings.TOUR_STATUS))
    return leaves, tours


def _absent_color():
    color = AttendanceStatusColor.objects.filter(status=settings.ABSENT).values_list("color_hex", flat=True).first()
    return color or ABSENT_COLOR


def _item(user, row, leaves, tours, absent_color, has_open_gaps):
    category = CATEGORIES.get(row.notification_type, OTHER)
    color, code, route, action = None, None, None, False

    if category == ATTENDANCE:
        kind, title = _attendance_kind(row)
        color = absent_color
        route = app_route(row)
        action = kind in GAP_KINDS and has_open_gaps
    elif row.go_route_mobile in (APPROVALS_ROUTE, APPROVALS_TOURS_ROUTE):
        # The daily reminder is about the queue, not one record.
        kind, title, route = "review", "Waiting for Your Decision", app_route(row)
    elif category == OTHER:
        kind, title = "info", "Comp-Off Update" if row.notification_type == settings.CO_STATUS else "Update"
    else:
        record = (leaves if category == LEAVE else tours).get(row.related_object_id)
        owner = (record.appliedBy_id if category == LEAVE else record.applied_by_id) if record else None
        is_reviewer = owner is not None and owner != user.pk
        noun = "Leave" if category == LEAVE else "Tour"
        kind, title = _workflow_kind(row.message.lower(), noun, is_reviewer)
        if category == LEAVE:
            color = record.leave_type.color_hex if record else None
            code = record.leave_type.leave_type_short_code if record else None
            awaiting = LEAVE_AWAITING
        else:
            color = TOUR_COLOR
            awaiting = tour_approval.AWAITING
        if record:
            route = app_route(row)  # None for a deleted record: the row just doesn't open
            action = is_reviewer and kind in REVIEW_KINDS and record.status in awaiting

    return {
        "id": row.pk,
        "title": title,
        "message": row.message,
        "category": category,
        "kind": kind,
        "color": color,
        "code": code,
        "route": route,
        "action_needed": action,
        "is_read": row.is_read,
        "timestamp": row.timestamp.isoformat(),
    }


def _received(user):
    return Notification.objects.filter(receiver=user)


def unread_count(user):
    return _received(user).filter(is_read=False).count()


def get_feed(user, *, filter_by, page):
    rows = _received(user).select_related("related_content_type").order_by("-timestamp", "-pk")
    if filter_by == "unread":
        rows = rows.filter(is_read=False)
    elif filter_by in FILTERS:
        rows = rows.filter(notification_type=FILTERS[filter_by])

    total = rows.count()
    start = (max(page, 1) - 1) * PAGE_SIZE
    chunk = list(rows[start : start + PAGE_SIZE])
    leaves, tours = _load_related(chunk)
    absent_color = _absent_color()
    has_open_gaps = AttendanceGap.objects.filter(user=user, is_open=True).exists()
    return {
        "results": [_item(user, row, leaves, tours, absent_color, has_open_gaps) for row in chunk],
        "page": max(page, 1),
        "total": total,
        "has_next": start + PAGE_SIZE < total,
        "unread_count": unread_count(user),
    }


def mark_read(user, notification_id):
    """False when the notification isn't this user's."""
    return bool(_received(user).filter(pk=notification_id).update(is_read=True))


def mark_all_read(user):
    return _received(user).filter(is_read=False).update(is_read=True)
