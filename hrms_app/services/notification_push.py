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


def app_route(notification):
    """In-app location for the notification (see the app's AppRoutes)."""
    _, _, prefix = _TYPES.get(notification.notification_type, (None, None, None))
    if prefix is None:
        return "/notifications"
    if prefix == "/attendance" or notification.related_object_id is None:
        return prefix
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
