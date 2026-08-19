from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import RegexValidator

from .core import CustomUser


class AppSetting(models.Model):
    key = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Setting Key",
        help_text="Unique key for identifying the application setting (e.g., 'REGULARIZATION_LIMIT')."
    )
    value = models.CharField(
        max_length=255,
        verbose_name="Setting Value",
        help_text="Value associated with the setting (e.g., '3' for the maximum number of times allowed)."
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Optional description of what this setting controls."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated",
        help_text="Timestamp of the last update to this setting."
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="allowed_app_settings",
        help_text="Only selected users can use this setting. Leave blank to allow all users."
    )
    beyond_policy = models.BooleanField(
        default=True,
        verbose_name="Allowed Beyond Policy",
        help_text="Indicates whether this setting is allowed beyond policy or not."
    )

    class Meta:
        verbose_name = "Application Setting"
        verbose_name_plural = "Application Settings"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key}: {self.value} (Active: {self.beyond_policy})"


class FormProgress(models.Model):
    STATUS_CHOICES = [
        ("in-progress", "In Progress"),
        ("completed", "Completed"),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    step = models.CharField(max_length=255)
    data = models.JSONField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in-progress"
    )
    timestamp = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(
        auto_now=True, blank=True, null=True, verbose_name=_("Updated At")
    )

    def __str__(self):
        return f"{self.user.username} - {self.step} ({self.status})"


class SentEmail(models.Model):
    recipient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="sent_emails"
    )
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emails_sent",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=settings.SENT_MAIL_STATUS_CHOICES,
        default=settings.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Email to {self.recipient.email} - {self.subject}"

    class Meta:
        db_table = "tbl_sent_email"
        managed = True
        verbose_name = _("Sent Mail")
        verbose_name_plural = _("Sent Mails")


from django.core.validators import RegexValidator
class EmailOTP(models.Model):
    """
    Stores OTPs for email verification purposes.
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="email_otps",
        verbose_name=_("User"),
        help_text=_("The user this OTP is associated with.")
    )

    email = models.EmailField(
        verbose_name=_("Email Address"),
        help_text=_("The email address to which the OTP was sent.")
    )

    otp = models.CharField(
        max_length=6,
        verbose_name=_("OTP"),
        validators=[
            RegexValidator(r'^\d{6}$', message=_("OTP must be a 6-digit number."))
        ],
        help_text=_("The one-time password sent to the email.")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The timestamp when the OTP was generated.")
    )

    verified = models.BooleanField(
        default=False,
        verbose_name=_("Is Verified"),
        help_text=_("Indicates whether the OTP was successfully verified.")
    )

    class Meta:
        verbose_name = _("Email OTP")
        verbose_name_plural = _("Email OTPs")
        indexes = [
            models.Index(fields=["user", "email"]),
            models.Index(fields=["otp"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.email} ({'verified' if self.verified else 'pending'})"

    def is_expired(self, expiry_minutes=10):
        """
        Check if the OTP is expired based on the expiry time.
        """
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expiry_minutes)
