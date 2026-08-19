from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

from .core import CustomUser
from datetime import datetime, timedelta
from django.utils.timezone import make_aware, is_naive,now


def make_datetime_aware(date, time):
    """Helper to combine date and time into a timezone-aware datetime."""
    naive_datetime = datetime.combine(date, time or datetime.min.time())
    return make_aware(naive_datetime) if is_naive(naive_datetime) else naive_datetime


class UserTour(models.Model):
    applied_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="tours",
        verbose_name=_("Applied By"),
    )
    short_code = models.CharField(
        max_length=10,
        verbose_name=_("Short Code"),
        default="T",
        help_text=_("Short code for the tour to show in the report"),
    )
    from_destination = models.CharField(
        max_length=255,
        verbose_name=_("From Destination"),
        help_text=_("Enter the location from which the tour starts."),
    )
    to_destination = models.CharField(
        max_length=255,
        verbose_name=_("To Destination"),
        help_text=_("Enter the destination where the tour ends."),
    )
    start_date = models.DateField(
        verbose_name=_("Start Date"),
        help_text=_("Select the start date of the tour."),
    )
    start_time = models.TimeField(
        verbose_name=_("Start Time"),
        blank=True,
        null=True,
        help_text=_("Select the start time of the tour."),
    )
    end_date = models.DateField(
        verbose_name=_("End Date"),
        help_text=_("Select the end date of the tour."),
    )
    end_time = models.TimeField(
        verbose_name=_("End Time"),
        blank=True,
        null=True,
        help_text=_("Select the end time of the tour."),
    )
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    remarks = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Remarks"),
        help_text=_("Any additional notes or comments about the tour."),
    )
    status = models.CharField(
        max_length=50,
        choices=settings.TOUR_STATUS_CHOICES,
        default=settings.PENDING,
        verbose_name=_("Status"),
        help_text=_("Current status of the tour."),
    )
    extended_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Extended End Date"),
        help_text=_("If applicable, enter the new end date after extension."),
    )
    extended_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Extended End Time"),
        help_text=_("If applicable, enter the new end time after extension."),
    )
    bills_submitted = models.BooleanField(
        default=False,
        verbose_name=_("Bills Submitted"),
        help_text=_("Indicate whether bills related to the tour have been submitted."),
    )
    slug = models.SlugField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("A unique identifier for the tour, used in URLs."),
    )
    approval_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=settings.APPROVAL_TYPE_CHOICES,
        verbose_name=_("Approval Type"),
        help_text=_("Select the type of approval required for this tour."),
    )
    total = models.TimeField(
        help_text=_(
            "The total duration of the tour from start date & time to end date & time in hours and minutes."
        ),
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"Tour {self.id} by {self.applied_by.username}"

    @property
    def is_editable(self):
        """Check if tour can be edited"""
        return self.status == 'pending'
    
    @property
    def is_approvable(self):
        """Check if tour can be approved"""
        return self.status == 'pending'
    @property
    def is_extendable(self):
        """Check if tour can be extended by employee"""
        return self.status == 'approved'
    
    @property
    def is_cancellable(self):
        """Check if tour can be cancelled"""
        return self.status in ['pending', 'approved', 'extended']
    
    @property
    def formatted_duration(self):
        """
        Returns total duration as a string: '2 Days : 5 Hrs'
        """
        if not (self.start_date and self.start_time):
            return "N/A"

        # 1. Construct Start DateTime
        start_dt = datetime.combine(self.start_date, self.start_time)

        # 2. Construct End DateTime (Prioritize Extended)
        if self.extended_end_date and self.extended_end_time:
            end_dt = datetime.combine(self.extended_end_date, self.extended_end_time)
        elif self.end_date and self.end_time:
            end_dt = datetime.combine(self.end_date, self.end_time)
        else:
            return "N/A"

        # 3. Calculate Duration
        duration = end_dt - start_dt
        
        # 4. Extract Days and Hours
        days = duration.days
        # duration.seconds only holds the "remainder" seconds (0 to 86399)
        # so we convert that remainder into hours
        hours = duration.seconds // 3600 

        return f"{days}d : {hours}h"

    def save(self, *args, **kwargs):
        """
        Override the save method to calculate the total duration.
        Total is calculated as the difference between start and end or extended end.
        """
        from datetime import timedelta, time
        from django.utils.timezone import make_aware

        if self.start_date and self.start_time:
            start_datetime = make_aware(
                datetime.combine(self.start_date, self.start_time)
            )
            # Use extended end date/time if available, else fallback to end date/time
            if self.extended_end_date and self.extended_end_time:
                end_datetime = make_aware(
                    datetime.combine(self.extended_end_date, self.extended_end_time)
                )
            elif self.end_date and self.end_time:
                end_datetime = make_aware(
                    datetime.combine(self.end_date, self.end_time)
                )
            else:
                end_datetime = None

            if end_datetime:
                # Calculate the total duration
                duration = end_datetime - start_datetime
                total_seconds = duration.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                self.total = time(hour=hours % 24, minute=minutes, second=seconds)
            else:
                self.total = None 
        super().save(*args, **kwargs)

    def approve(self, action_by, reason=None):
        self.status = settings.APPROVED
        self.save(update_fields=["status", "updated_at"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Approved by {action_by.username}. Reason: {reason}",
        )

    def reject(self, action_by, reason=None):
        self.status = settings.REJECTED
        self.save(update_fields=["status", "updated_at"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Rejected by {action_by.username}. Reason: {reason}",
        )

    def cancel(self, action_by, reason=None):
        self.status = settings.CANCELLED
        self.save(update_fields=["status", "updated_at"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Cancelled by {action_by.username}. Reason: {reason}",
        )

    def pending_cancel(self, action_by, reason=None):
        self.status = settings.PENDING_CANCELLATION
        self.save(update_fields=["status", "updated_at"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Pending Cancellation by {action_by.username}. Reason: {reason}",
        )

    def complete(self, action_by, reason=None):
        comments = reason or "Tour completed"
        self.status = settings.COMPLETED
        self.save(update_fields=["status", "updated_at"])
        TourStatusLog.create_log(
            tour=self, action_by=action_by, action=self.status, comments=comments
        )

    def extend(self, action_by, reason=None):
        self.status = settings.EXTENDED
        self.save(
            update_fields=[
                "status",
                "extended_end_date",
                "extended_end_time",
                "updated_at",
            ]
        )
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Tour extended to {self.extended_end_date} {self.extended_end_time}. Reason: {reason}",
        )

    class Meta:
        db_table = "tbl_user_tours"
        managed = True
        verbose_name = _("User Tour")
        verbose_name_plural = _("Users' Tours")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["end_date"]),
            models.Index(fields=["slug"]),
        ]
        unique_together = (
            "applied_by",
            "slug",
        )  # Prevents duplicate slugs for the same user


class TourStatusLog(models.Model):
    tour = models.ForeignKey(
        UserTour, on_delete=models.CASCADE, related_name="logs", verbose_name=_("Tour")
    )
    action_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, verbose_name=_("Action By")
    )
    action_by_name = models.CharField(
        max_length=255, verbose_name=_("Action By Name"), blank=True, null=True
    )
    action_by_email = models.EmailField(
        verbose_name=_("Action By Email"), blank=True, null=True
    )
    action = models.CharField(
        max_length=100, verbose_name=_("Action"), blank=True, null=True
    )
    status = models.CharField(
        max_length=50,
        choices=settings.TOUR_STATUS_CHOICES,
        default=settings.PENDING,
        verbose_name=_("Status"),
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    comments = models.TextField(null=True, blank=True, verbose_name=_("Comments"))

    def __str__(self):
        return f"Log {self.id} for Tour {self.tour.id}"

    class Meta:
        db_table = "tbl_tour_status_log"
        managed = True
        verbose_name = _("Tour Status Log")
        verbose_name_plural = _("Tour Status Logs")

    @classmethod
    def create_log(cls, tour, action_by, action, comments=""):
        """
        Creates a log entry for a tour.

        :param tour_instance: The instance of UserTour related to this log.
        :param status: The status to log.
        :param comments: Optional comments to add to the log.
        :return: The created TourStatusLog instance.
        """
        cls.objects.create(
            tour=tour,
            action_by=action_by,
            action_by_name=f"{action_by.first_name} {action_by.last_name}",
            action_by_email=action_by.email,
            action=action,
            comments=comments,
        )

_DATETIME_FIELDS = ["start_date", "start_time", "end_date", "end_time"]


class TourDateTimeChangeLog(models.Model):
    tour       = models.ForeignKey(
        "UserTour",
        on_delete=models.CASCADE,
        related_name="datetime_change_logs",
        verbose_name=_("Tour"),
    )
    changed_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        related_name="tour_datetime_changes",
        verbose_name=_("Changed By"),
    )

    # ── Previous ──────────────────────────────────────────────────────────
    previous_start_date = models.DateField(null=True, blank=True)
    previous_start_time = models.TimeField(null=True, blank=True)
    previous_end_date   = models.DateField(null=True, blank=True)
    previous_end_time   = models.TimeField(null=True, blank=True)

    # ── New ───────────────────────────────────────────────────────────────
    new_start_date = models.DateField(null=True, blank=True)
    new_start_time = models.TimeField(null=True, blank=True)
    new_end_date   = models.DateField(null=True, blank=True)
    new_end_time   = models.TimeField(null=True, blank=True)

    changed_fields = models.JSONField(default=list)
    reason         = models.TextField(null=True, blank=True, verbose_name=_("Reason"))
    changed_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("Tour Date/Time Change Log")
        verbose_name_plural = _("Tour Date/Time Change Logs")
        ordering            = ["-changed_at"]

    def __str__(self):
        return f"Change on {self.tour} at {self.changed_at:%Y-%m-%d %H:%M}"

    @classmethod
    def create_from_diff(cls, tour, previous_snapshot, changed_by, reason=""):
        """
        Snapshot `previous_snapshot` (dict) vs current `tour` state
        and persist only if something actually changed.
        Returns the log instance or None if nothing changed.
        """
        changed_fields = [
            f for f in _DATETIME_FIELDS
            if previous_snapshot.get(f) != getattr(tour, f)
        ]
        if not changed_fields:
            return None

        return cls.objects.create(
            tour=tour,
            changed_by=changed_by,
            previous_start_date=previous_snapshot["start_date"],
            previous_start_time=previous_snapshot["start_time"],
            previous_end_date=previous_snapshot["end_date"],
            previous_end_time=previous_snapshot["end_time"],
            new_start_date=tour.start_date,
            new_start_time=tour.start_time,
            new_end_date=tour.end_date,
            new_end_time=tour.end_time,
            changed_fields=changed_fields,
            reason=reason,
        )
        
class Bill(models.Model):
    tour = models.ForeignKey(UserTour, on_delete=models.CASCADE, verbose_name=_("Tour"))
    bill_amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Bill Amount")
    )
    bill_date = models.DateField(verbose_name=_("Bill Date"))
    bill_details = models.TextField(verbose_name=_("Bill Details"))
    bill_document = models.FileField(
        upload_to="bills/", verbose_name=_("Bill Document")
    )
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="created_tour_bills",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="updated_tour_bills",
        null=True,
        blank=True,
        verbose_name=_("Updated By"),
    )

    def save(self, *args, **kwargs):
        created_by = kwargs.pop("created_by", None)
        updated_by = kwargs.pop("updated_by", None)
        if not self.pk and created_by:
            self.created_by = created_by
        if updated_by:
            self.updated_by = updated_by
        super(Bill, self).save(*args, **kwargs)

    def __str__(self):
        return f"Bill {self.id} for Tour {self.tour.id}"

    class Meta:
        db_table = "tbl_tour_bill"
        managed = True
        verbose_name = _("Tour Bill")
        verbose_name_plural = _("Tour Bills")


