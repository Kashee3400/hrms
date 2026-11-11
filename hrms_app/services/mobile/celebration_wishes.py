"""
Wishing a colleague from the app on their birthday or anniversary. Only on the
day itself, once per colleague and occasion. The colleague gets an in-app
notification, a push and a mail; only they can read the messages.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from hrms_app.models import CelebrationWish, Notification
from hrms_app.services.mobile.celebrations import occasions_on
from hrms_app.tasks import send_leave_application_email

MAX_MESSAGE = 300
OCCASION_WORDS = {
    CelebrationWish.BIRTHDAY: "a Happy Birthday",
    CelebrationWish.MARRIAGE: "a Happy Wedding Anniversary",
    CelebrationWish.WORK: "a Happy Work Anniversary",
}
SUBJECTS = {
    CelebrationWish.BIRTHDAY: "Happy Birthday from",
    CelebrationWish.MARRIAGE: "Happy Anniversary from",
    CelebrationWish.WORK: "Happy Work Anniversary from",
}


def _name(user):
    return user.get_full_name() or user.username


def _queue_mail(subject, body, email):
    try:
        send_leave_application_email.delay(subject, body, [email])
    except Exception:
        pass  # the in-app notification and push still reach them


def send_wish(sender, receiver_id, kind, message, today=None):
    """Returns an error message, or None when the wish was sent."""
    today = today or timezone.localdate()
    message = (message or "").strip()
    if not message:
        return "Please write a message."
    if len(message) > MAX_MESSAGE:
        return f"Keep the message under {MAX_MESSAGE} characters."
    receiver = get_user_model().objects.filter(pk=receiver_id, is_active=True).first()
    if receiver is None:
        return "Employee not found."
    if receiver.pk == sender.pk:
        return "You can't wish yourself."
    if kind not in occasions_on(receiver, today):
        return "There's nothing to celebrate for this employee today."

    try:
        with transaction.atomic():
            CelebrationWish.objects.create(
                sender=sender, receiver=receiver, kind=kind, occasion_date=today, message=message
            )
            text = f"{_name(sender)} wished you {OCCASION_WORDS[kind]}: {message}"
            Notification.objects.create(
                sender=sender, receiver=receiver, message=text[:255], target_url="/"
            )
            email = receiver.official_email or receiver.email
            if email:
                body = f"Dear {receiver.first_name or _name(receiver)},\n\n{message}\n\nWarm wishes,\n{_name(sender)}"
                subject = f"{SUBJECTS[kind]} {_name(sender)}"
                transaction.on_commit(lambda: _queue_mail(subject, body, email))
    except IntegrityError:
        return "You have already wished them today."
    return None


def wishes_received(user, kind, today=None):
    """Today's wishes to ``user`` for ``kind``, newest first."""
    today = today or timezone.localdate()
    rows = CelebrationWish.objects.filter(receiver=user, kind=kind, occasion_date=today).select_related("sender")
    return [
        {
            "name": _name(row.sender),
            "message": row.message,
            "at": timezone.localtime(row.created_at).isoformat(),
        }
        for row in rows
    ]
