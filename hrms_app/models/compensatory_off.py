import uuid
from datetime import timedelta

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models import Sum

from .core import CustomUser
from .leave import LeaveType


class CompensatoryOff(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name="Unique ID"
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="compensatory_offs",
        verbose_name="User",
        help_text="The employee who earned this compensatory off.",
    )
    worked_on = models.DateField(
        verbose_name="Worked On", help_text="Date the employee worked."
    )
    expiry_date = models.DateField(
        verbose_name="Expiry Date", help_text="Date the compensatory off expires."
    )
    reason = models.TextField(
        null=True,
        blank=True,
        verbose_name="Reason",
        help_text="Reason for working on the day and earning compensatory off.",
    )
    hours_earned = models.FloatField(
        validators=[MinValueValidator(0.5)],
        null=True,
        blank=True,
        verbose_name="Hours Earned",
        default=1.0,
    )

    status = models.CharField(
        max_length=20,
        choices=settings.CO_STATUS_CHOICES,
        default=settings.OPEN,
        verbose_name="Status",
        help_text="The current status of the compensatory off.",
    )

    # Additional fields for advanced management
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Leave Type",
    )
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_comp_offs",
        verbose_name="Approved By",
    )
    comments = models.TextField(
        null=True, blank=True, verbose_name="Comments", help_text="Additional notes"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Automatically set expiry date if not provided (customizable logic)
        if not self.expiry_date:
            self.expiry_date = self.worked_on + timedelta(
                days=settings.CO_EXPIRY_DAYS
            )  # Replace with your logic

        # Update status to 'expired' if expiry date has passed and status is still 'open'
        if self.status == "open" and self.expiry_date < timezone.now().date():
            self.status = "expired"

        super(CompensatoryOff, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - CO on {self.worked_on} ({self.hours_earned} hours) - (Status: {self.status})"

    @classmethod
    def get_available_balance(cls, user):
        """
        Calculates the total available compensatory off hours for a user.
        """
        approved_comp_offs = cls.objects.filter(user=user, status="open")
        total_hours = (
            approved_comp_offs.aggregate(total_hours=Sum("hours_earned"))["total_hours"]
            or 0.0
        )
        return total_hours


class CompensatoryOffLog(models.Model):
    compensatory_off = models.ForeignKey(
        "CompensatoryOff",
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name=_("Compensatory Off"),
    )
    action_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, verbose_name=_("Action By")
    )
    action_by_name = models.CharField(max_length=255, verbose_name=_("Action By Name"))
    action_by_email = models.EmailField(verbose_name=_("Action By Email"))
    action = models.CharField(max_length=100, verbose_name=_("Action"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    def __str__(self):
        return f"{self.action} by {self.action_by_name} on {self.timestamp}"

    @classmethod
    def create_log(cls, compensatory_off, action_by, action, notes=""):
        cls.objects.create(
            compensatory_off=compensatory_off,
            action_by=action_by,
            action_by_name=f"{action_by.first_name} {action_by.last_name}",
            action_by_email=action_by.email,
            action=action,
            notes=notes,
        )

    class Meta:
        db_table = "tbl_compensatory_off_log"
        managed = True
        verbose_name = _("Compensatory Off Log")
        verbose_name_plural = _("Compensatory Off Logs")
        ordering = ["-timestamp"]


