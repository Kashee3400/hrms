from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ApprovalMail(models.Model):
    """A beyond-policy approval request the employee emailed from the app.
    The decision itself stays on email with the competent authority."""

    ATTENDANCE = "attendance"
    LEAVE_POLICY = "leave_policy"
    TOUR_POLICY = "tour_policy"
    KIND_CHOICES = [
        (ATTENDANCE, _("Attendance")),
        (LEAVE_POLICY, _("Leave Policy")),
        (TOUR_POLICY, _("Tour Policy")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_mails",
        verbose_name=_("Employee"),
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name=_("Kind"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))
    subject = models.CharField(max_length=255, verbose_name=_("Subject"))
    body = models.TextField(verbose_name=_("Body"))
    reason = models.TextField(verbose_name=_("Reason"))
    to_email = models.CharField(max_length=255, verbose_name=_("To"))
    cc_emails = models.JSONField(default=list, verbose_name=_("CC"))
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Sent At"))

    class Meta:
        db_table = "tbl_approval_mail"
        verbose_name = _("Approval Mail")
        verbose_name_plural = _("Approval Mails")
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["user", "start_date"], name="idx_approval_mail_user_date")]

    def __str__(self):
        return f"{self.user.username} {self.kind} {self.start_date}"


class AttendanceGap(models.Model):
    """One working day an employee still has to account for. One row per
    employee and date, so a re-run of the daily scan never repeats a reminder."""

    ABSENT = "absent"
    NO_RECORD = "no_record"
    MISSING_PUNCH = "missing_punch"
    KIND_CHOICES = [
        (ABSENT, _("Absent")),
        (NO_RECORD, _("No Attendance Record")),
        (MISSING_PUNCH, _("Missing Punch-out")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_gaps",
        verbose_name=_("Employee"),
    )
    date = models.DateField(verbose_name=_("Date"))
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name=_("Kind"))
    is_open = models.BooleanField(default=True, verbose_name=_("Is Open"))
    first_notified_on = models.DateField(null=True, blank=True, verbose_name=_("First Reminder"))
    last_day_notified_on = models.DateField(null=True, blank=True, verbose_name=_("Last Day Reminder"))
    expired_notified_on = models.DateField(null=True, blank=True, verbose_name=_("Expiry Notice"))
    approval_mail = models.ForeignKey(
        ApprovalMail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gaps",
        verbose_name=_("Approval Mail"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        db_table = "tbl_attendance_gap"
        verbose_name = _("Attendance Gap")
        verbose_name_plural = _("Attendance Gaps")
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_attendance_gap_user_date")
        ]
        indexes = [models.Index(fields=["is_open", "date"], name="idx_attendance_gap_open_date")]

    def __str__(self):
        return f"{self.user.username} {self.date} {self.kind}"
