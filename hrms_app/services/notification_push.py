"""
Turns an in-app ``Notification`` row into a mobile push: title, Android
channel and the app route to open on tap.
"""
from django.conf import settings

from hrms_app.services.fcm import send_to_user

# notification_type -> (title, android channel, app route prefix)
_TYPES = {
    settings.LEAVE_STATUS: ("Leave Update", "leave_tour", "/leaves"),
    settings.TOUR_STATUS: ("Tour Update", "leave_tour", "/tours"),
    settings.CO_STATUS: ("Comp-Off Update", "leave_tour", None),
    settings.ATTENDANCE_REGULARISATION: ("Attendance", "attendance", "/attendance"),
}

# The app's list of days to act on; stored in Notification.go_route_mobile.
ATTENDANCE_GAPS_ROUTE = "/attendance/gaps"

# A reviewer's queue, for the daily reminder.
APPROVALS_ROUTE = "/approvals"
APPROVALS_TOURS_ROUTE = "/approvals?tab=tours"

# Reviewer-side screens for the same records (see the app's AppRoutes).
_REVIEW_PREFIXES = {
    settings.LEAVE_STATUS: "/approvals/leaves",
    settings.TOUR_STATUS: "/approvals/tours",
}


def _applicant_id(notification):
    """Who applied for the leave/tour the notification is about."""
    obj = notification.related_object
    return getattr(obj, "appliedBy_id", None) or getattr(obj, "applied_by_id", None)


def app_route(notification):
    """In-app location for the notification (see the app's AppRoutes).

    The applicant opens their own application; anyone else (the manager)
    opens the review screen, which has the approve/reject actions.
    """
    if notification.go_route_mobile in (ATTENDANCE_GAPS_ROUTE, APPROVALS_ROUTE, APPROVALS_TOURS_ROUTE):
        return notification.go_route_mobile
    _, _, prefix = _TYPES.get(notification.notification_type, (None, None, None))
    if prefix is None:
        return "/notifications"
    if prefix == "/attendance" or notification.related_object_id is None:
        return prefix
    review_prefix = _REVIEW_PREFIXES.get(notification.notification_type)
    if review_prefix and _applicant_id(notification) not in (None, notification.receiver_id):
        prefix = review_prefix
    return f"{prefix}/{notification.related_object_id}"


def push_notification_to_device(notification):
    if notification.receiver_id is None:
        return 0
    title, channel, _ = _TYPES.get(notification.notification_type, ("K-HRMS", "general", None))
    return send_to_user(
        notification.receiver,
        title=title,
        body=notification.message,
        channel=channel,
        data={
            "type": notification.notification_type,
            "route": app_route(notification),
            "notification_id": notification.pk,
        },
    )
