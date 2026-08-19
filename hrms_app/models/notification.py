from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .core import CustomUser


class Notification(models.Model):
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="Sender",
        related_name="notifications_sent",
        help_text="The user who sent the notification.",
    )

    receiver = models.ForeignKey(
        CustomUser,
        related_name="notifications",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Receiver",
        help_text="The user who receives the notification.",
    )

    message = models.CharField(
        max_length=255,
        verbose_name="Notification Message",
        help_text="The content of the notification.",
    )

    notification_type = models.CharField(
        max_length=50,
        choices=settings.NOTIFICATION_TYPES,
        null=True,
        blank=True,
        verbose_name="Notification Type",
        help_text="The type of notification being sent.",
    )

    # Fields to store related object information
    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Related Object ID",
        help_text="The ID of the related object associated with this notification.",
    )

    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Related Content Type",
        help_text="The type of the related object (model) this notification is linked to.",
    )

    related_object = GenericForeignKey("related_content_type", "related_object_id")

    target_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Target URL",
        help_text="The URL for web navigation related to this notification.",
    )

    payload_data = models.JSONField(
        null=True, blank=True, verbose_name="Payload Data"
    )  # Additional data for custom platform notification formats
    go_route_mobile = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Mobile Deep Link",
        help_text="The mobile deep link for navigating to the related content.",
    )
    desktop_notification_data = models.JSONField(
        null=True, blank=True, verbose_name="Desktop Notification Data"
    )  # Data for specific desktop notification libraries

    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Timestamp",
        help_text="The time when the notification was created.",
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name="Read Status",
        help_text="Indicates whether the notification has been read.",
    )

    def __str__(self):
        return f"{self.notification_type}: {self.message}"

    class Meta:
        db_table = "tbl_notification"
        managed = True
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"


class NotificationSetting(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        help_text=_("The user to whom these notification settings apply."),
    )

    receive_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Notifications"),
        help_text=_("Enable or disable all notifications."),
    )
    receive_sound_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Sound Notifications"),
        help_text=_("Enable or disable sound for notifications."),
    )
    receive_desktop_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Desktop Notifications"),
        help_text=_("Enable or disable notifications on desktop."),
    )
    receive_mobile_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Mobile Notifications"),
        help_text=_("Enable or disable notifications on mobile."),
    )

    receive_message_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Message Notifications"),
        help_text=_("Enable or disable notifications for new messages."),
    )
    receive_mention_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Mention Notifications"),
        help_text=_("Enable or disable notifications when you are mentioned."),
    )
    receive_like_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Like Notifications"),
        help_text=_("Enable or disable notifications for likes."),
    )
    receive_comment_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Receive Comment Notifications"),
        help_text=_("Enable or disable notifications for new comments."),
    )

    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ("immediate", _("Immediate")),
            ("hourly", _("Hourly")),
            ("daily", _("Daily")),
            ("weekly", _("Weekly")),
        ],
        default="immediate",
        verbose_name=_("Notification Frequency"),
        help_text=_("Choose how often to receive notifications."),
    )

    notification_importance = models.CharField(
        max_length=20,
        choices=[
            ("high", _("High")),
            ("medium", _("Medium")),
            ("low", _("Low")),
        ],
        default="medium",
        verbose_name=_("Notification Importance"),
        help_text=_("Set the importance level for notifications."),
    )

    desktop_notification_sound = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Desktop Notification Sound"),
        help_text=_("Specify the sound file for desktop notifications."),
    )
    mobile_notification_sound = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Mobile Notification Sound"),
        help_text=_("Specify the sound file for mobile notifications."),
    )

    # Do Not Disturb mode
    do_not_disturb_mode = models.BooleanField(
        default=False,
        verbose_name=_("Do Not Disturb Mode"),
        help_text=_("Enable to mute notifications during specified hours."),
    )

    # Notification history
    notification_history = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Notification History"),
        help_text=_("Log of previous notifications sent to the user."),
    )

    def __str__(self):
        return f"Notification settings for {self.user.username}"

    class Meta:
        db_table = "tbl_notification_settings"
        managed = True
        verbose_name = _("Notification Setting")
        verbose_name_plural = _("Notification Settings")
        ordering = ["user"]  # Orders settings by user
        unique_together = ("user",)  # Ensure only one notification setting per user
        indexes = [
            models.Index(
                fields=["user"], name="user_idx"
            ),  # Index for faster lookups by user
        ]

