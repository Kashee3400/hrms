"""
Firebase Cloud Messaging for the mobile app.

Setup (server): `pip install firebase-admin` and set FIREBASE_CREDENTIALS in
.env to the path of the Firebase service-account JSON (project kashee-hr).
Without it, sending is skipped with a log line - nothing else breaks.

Payload contract with the app (see the app's README):
    notification: {title, body}
    data: {type, route, notification_id}
    android.notification.channel_id: leave_tour | attendance | general
"""
import logging

from decouple import config

from hrms_app.models import DeviceToken

logger = logging.getLogger(__name__)

_app = None


def _firebase():
    """Initialises firebase_admin once. Returns the messaging module or None."""
    global _app
    path = config("FIREBASE_CREDENTIALS", default="")
    if not path:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError:
        logger.warning("firebase-admin is not installed; push disabled.")
        return None
    if _app is None:
        try:
            _app = firebase_admin.get_app()
        except ValueError:
            _app = firebase_admin.initialize_app(credentials.Certificate(path))
    return messaging


def send_to_user(user, *, title, body, data=None, channel="general"):
    """Sends to every active device of ``user``. Returns the number delivered.

    Tokens FCM reports as dead are deactivated so they aren't retried.
    """
    messaging = _firebase()
    if messaging is None:
        logger.info("FCM not configured; skipped push to user %s", user.pk)
        return 0

    tokens = list(
        DeviceToken.objects.filter(user=user, is_active=True).values_list("token", flat=True)
    )
    if not tokens:
        return 0

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        # FCM data values must be strings.
        data={key: str(value) for key, value in (data or {}).items() if value is not None},
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id=channel,
                click_action="FLUTTER_NOTIFICATION_CLICK",
            ),
        ),
    )
    response = messaging.send_each_for_multicast(message)

    dead = [
        token
        for token, result in zip(tokens, response.responses)
        if not result.success
        and isinstance(result.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError))
    ]
    if dead:
        DeviceToken.objects.filter(token__in=dead).update(is_active=False)
    for token, result in zip(tokens, response.responses):
        if not result.success and token not in dead:
            logger.warning("FCM send failed for user %s: %s", user.pk, result.exception)
    return response.success_count
