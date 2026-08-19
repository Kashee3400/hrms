from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError


class ShiftTiming(models.Model):
    start_time = models.TimeField(
        verbose_name=_("Start Time"), help_text=_("Enter the start time for the shift.")
    )
    end_time = models.TimeField(
        verbose_name=_("End Time"), help_text=_("Enter the end time for the shift.")
    )
    grace_time = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_("Grace Time (minutes)"),
        help_text=_("Enter the grace time for late arrivals (in minutes, optional)."),
    )
    grace_start_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("Grace Start Time"),
        help_text=_("Enter the start time for the grace period (optional)."),
    )
    grace_end_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("Grace End Time"),
        help_text=_("Enter the end time for the grace period (optional)."),
    )
    break_start_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("Break Start Time"),
        help_text=_("Enter the start time for the break (optional)."),
    )
    break_end_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("Break End Time"),
        help_text=_("Enter the end time for the break (optional)."),
    )
    break_duration = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_("Break Duration (minutes)"),
        help_text=_(
            "The calculated break duration in minutes, automatically set when both start and end times are provided."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether this shift timing is active."),
    )
    role = models.ForeignKey(
        "Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Role"),
        help_text=_("Assign this shift to a specific role (optional)."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )

    def __str__(self):
        return (
            f'{self.start_time.strftime("%I:%M %p")} - {self.end_time.strftime("%I:%M %p")}'
        )

    def save(self, *args, **kwargs):
        """
        Override the save method to automatically calculate break duration
        when break_start_time and break_end_time are provided.
        """
        if self.break_start_time and self.break_end_time:
            break_start = timezone.datetime.combine(
                timezone.now().date(), self.break_start_time
            )
            break_end = timezone.datetime.combine(
                timezone.now().date(), self.break_end_time
            )

            # Validate that break_end_time is after break_start_time
            if break_start >= break_end:
                raise ValidationError(
                    _("Break end time must be after break start time.")
                )

            # Calculate and set break duration in minutes
            duration = break_end - break_start
            self.break_duration = duration.total_seconds() // 60
        else:
            self.break_duration = None  # Reset if break times are not provided

        super().save(*args, **kwargs)

    class Meta:
        db_table = "tbl_shift_timing"
        verbose_name = _("Shift Timing")
        verbose_name_plural = _("Shift Timings")
        indexes = [
            models.Index(fields=["start_time", "end_time"], name="idx_shift_timing"),
        ]


class EmployeeShift(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name=_("Employee"),
        help_text=_("Select the employee associated with this shift."),
    )
    shift_timing = models.ForeignKey(
        "ShiftTiming",
        on_delete=models.CASCADE,
        verbose_name=_("Shift Timing"),
        help_text=_("Select the shift timing for the employee."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created By"),
        related_name="shift_created",
        help_text=_("The user who created this shift record."),
    )

    class Meta:
        db_table = "tbl_employee_shift"
        managed = True
        verbose_name = _("Employee Shift")
        verbose_name_plural = _("Employee Shifts")
        indexes = [
            models.Index(
                fields=["employee", "shift_timing"], name="idx_employee_shift"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "shift_timing"], name="unique_employee_shift"
            ),
        ]

    def __str__(self):
        return f"{self.shift_timing}"

    def clean(self):
        if self.employee.shifts.filter(shift_timing=self.shift_timing).exists():
            raise ValidationError(
                _("This employee already has a shift with the selected timing.")
            )


