import random
import string
from datetime import datetime

from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

from .core import CustomUser
from . import _current_year
from ..manager.leave_days import LeaveDayManager
from ..choices.leave import LeaveUnit, LeaveAccrualPeriod, LeaveExpiryPolicy


class LeaveLog(models.Model):
    leave_application = models.ForeignKey(
        "LeaveApplication",
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name=_("Leave Application"),
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
    def create_log(cls, leave_application, action_by, action, notes=""):
        cls.objects.create(
            leave_application=leave_application,
            action_by=action_by,
            action_by_name=f"{action_by.first_name} {action_by.last_name}",
            action_by_email=action_by.email,
            action=action,
            notes=notes,
        )

    class Meta:
        db_table = "tbl_leave_log"
        managed = True
        verbose_name = _("Leave Log")
        verbose_name_plural = _("Leave Logs")
        ordering = ["-timestamp"]


class LeaveApplication(models.Model):
    leave_type = models.ForeignKey(
        "LeaveType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_applications",
        verbose_name=_("Leave Type"),
    )
    applicationNo = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_("Application No"),
        help_text=_("Unique identifier for the leave application."),
    )
    appliedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leaves",
        verbose_name=_("Applied By"),
    )
    applyingDate = models.DateTimeField(auto_now_add=True, verbose_name=_("Applying Date"))
    startDate = models.DateTimeField(
        verbose_name=_("Start Date"), help_text=_("The date when the leave begins.")
    )
    endDate = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("End Date"),
        help_text=_(
            "The date when the leave ends. Leave can be of a single day or multiple days."
        ),
    )
     # 🔹 NEW: Short Leave Time Fields
    from_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time for Short Leave"
    )
    to_time = models.TimeField(
        null=True,
        blank=True,
        help_text="End time for Short Leave"
    )

    usedLeave = models.FloatField(
        verbose_name=_("Used Leave"),
        help_text=_("Total leave days used for this application."),
    )
    balanceLeave = models.FloatField(
        verbose_name=_("Balance Leave"),
        help_text=_("Remaining leave days available after this application."),
    )
    reason = models.TextField(
        blank=True, verbose_name=_("Reason"), help_text=_("Reason for applying leave.")
    )
    status = models.CharField(
        max_length=30,
        choices=settings.LEAVE_STATUS_CHOICES,
        default=settings.PENDING,
        verbose_name=_("Status"),
        help_text=_("Current status of the leave application."),
    )
    leave_address = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Leave Address"),
        help_text=_("Please provide the address."),
    )

    startDayChoice = models.CharField(
        max_length=20,
        default=settings.FULL_DAY,
        choices=settings.START_LEAVE_TYPE_CHOICES,
        verbose_name=_("Start Day Choice"),
        help_text=_(
            "Choose whether the leave starts at the beginning or the end of the day."
        ),
    )
    endDayChoice = models.CharField(
        max_length=20,
        default=settings.FULL_DAY,
        choices=settings.START_LEAVE_TYPE_CHOICES,
        verbose_name=_("End Day Choice"),
        help_text=_(
            "Choose whether the leave ends at the beginning or the end of the day."
        ),
    )
    updatedAt = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        editable=False,
        verbose_name=_("Slug"),
        help_text=_(
            "Automatically generated unique identifier for the leave application."
        ),
    )
        # Add a file upload field
    attachment = models.FileField(
        upload_to="leave_attachments/",
        blank=True,
        null=True,
        verbose_name=_("Attachment"),
        help_text=_("Upload an image or PDF file (optional)."),
    )

    is_leave_deducted = models.BooleanField(default=False)
    def is_short_leave(self) -> bool:
        return (
            self.leave_type is not None
            and getattr(self.leave_type, "leave_type_short_code", None) == "STL"
        )
    def get_short_leave_duration_hours(self) -> float:
        duration = self.get_short_leave_duration()
        if not duration:
            return 0.0

        return round(duration.total_seconds() / 3600, 2)
    def get_short_leave_duration_display(self) -> str:
        duration = self.get_short_leave_duration()
        if not duration:
            return "0 min"

        total_minutes = int(duration.total_seconds() / 60)
        hours, minutes = divmod(total_minutes, 60)

        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_short_leave_datetime_range(self):
        """
        Returns (from_datetime, to_datetime) or (None, None)
        """
        if not self.is_short_leave():
            return None, None

        if not self.from_time or not self.to_time:
            return None, None

        base_date = self.startDate.date()

        from_dt = datetime.combine(base_date, self.from_time)
        to_dt = datetime.combine(base_date, self.to_time)

        # Make timezone-aware if needed
        if timezone.is_aware(self.startDate):
            from_dt = timezone.make_aware(from_dt)
            to_dt = timezone.make_aware(to_dt)

        return from_dt, to_dt
    def get_short_leave_duration(self):
        """
        Returns timedelta or None
        """
        from_dt, to_dt = self.get_short_leave_datetime_range()

        if not from_dt or not to_dt:
            return None

        if to_dt <= from_dt:
            return None

        return to_dt - from_dt

    def save(self, *args, **kwargs):
        if self.startDate and self.endDate and self.startDate > self.endDate:
            raise ValidationError(_("Start date cannot be after end date."))
        if not self.applicationNo:
            self.applicationNo = self.generate_unique_application_no()

        if not self.slug:
            self.slug = self.generate_unique_slug()

        super().save(*args, **kwargs)  # Save first

    def generate_unique_application_no(self):
        """Generate a unique application number."""
        while True:
            random_str = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=4)
            )
            application_no = f"Leave/{self.leave_type.leave_type}/{random_str}"
            if not LeaveApplication.objects.filter(
                applicationNo=application_no
            ).exists():
                return application_no

    def generate_unique_slug(self):
        """Generate a unique slug based on the applicant's name and dates."""
        base_slug = f"{self.appliedBy.get_full_name()}-{self.startDate.strftime('%Y-%m-%d')}-{self.startDayChoice}"
        unique_slug = slugify(base_slug)
        num = 1
        while LeaveApplication.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{slugify(base_slug)}-{num}"
            num += 1
        return unique_slug

    def __str__(self):
        return f"Leave Application {self.applicationNo} for {self.appliedBy}"

    def approve_leave(self, action_by):
        return self.update_status(action_by, settings.APPROVED)

    def reject_leave(self, action_by):
        return self.update_status(action_by, settings.REJECTED)

    def cancel_leave(self, action_by):
        return self.update_status(action_by, settings.CANCELLED)

    def update_status(self, action_by, new_status):
        if (
            self.status in [settings.PENDING, settings.APPROVED]
            and new_status != settings.PENDING
        ):
            self.status = new_status
            self.save(update_fields=["status", "updatedAt"])
            LeaveLog.create_log(self, action_by, new_status)

    @classmethod
    def create_leave_application(
        cls,
        applied_by,
        start_date,
        end_date,
        used_leave,
        balance_leave,
        reason,
        start_day_choice,
        end_day_choice,
        leave_type=None,
    ):
        leave_application = cls.objects.create(
            appliedBy=applied_by,
            leave_type=leave_type,
            startDate=start_date,
            endDate=end_date,
            usedLeave=used_leave,
            balanceLeave=balance_leave,
            reason=reason,
            startDayChoice=start_day_choice,
            endDayChoice=end_day_choice,
        )
        LeaveLog.create_log(
            leave_application=leave_application,
            action_by=applied_by,
            action="Created",
            notes=reason,
        )

        return leave_application

    class Meta:
        db_table = "tbl_leave_application"
        managed = True
        verbose_name = _("Leave Application")
        verbose_name_plural = _("Leave Applications")
        indexes = [
            models.Index(
                fields=["appliedBy", "status"], name="idx_leave_application_status"
            ),
        ]


class LeaveDay(models.Model):
    leave_application = models.ForeignKey(
        LeaveApplication, on_delete=models.CASCADE, related_name="leave_days"
    )
    date = models.DateField(verbose_name=_("Date"))
    is_full_day = models.BooleanField(default=True, verbose_name=_("Is Full Day"))
    objects = LeaveDayManager()
    class Meta:
        unique_together = ("leave_application", "date")

class LeaveDayChoiceAdjustment(models.Model):
    """
    Store different combinations of start and end day choices along with adjustment values.
    """

    start_day_choice = models.CharField(
        max_length=20,
        choices=settings.START_LEAVE_TYPE_CHOICES,
        verbose_name="Start Day Choice",
    )
    end_day_choice = models.CharField(
        max_length=20,
        choices=settings.START_LEAVE_TYPE_CHOICES,
        verbose_name="End Day Choice",
    )
    adjustment_value = models.FloatField(verbose_name="Adjustment Value")

    def __str__(self):
        return f"{self.start_day_choice} to {self.end_day_choice} adjustment: {self.adjustment_value}"

    class Meta:
        unique_together = ("start_day_choice", "end_day_choice")
        verbose_name = "Leave Day Choice Adjustment"
        verbose_name_plural = "Leave Day Choice Adjustments"

class LeaveType(models.Model):
    # ------------------------
    # Basic Info
    # ------------------------

    leave_type = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Leave Type"),
        help_text=_("Name of the leave type (e.g. Sick Leave, Short Leave)."),
    )

    leave_type_short_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Leave Short Code"),
    )

    half_day_short_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Half Day Short Code"),
    )

    # ------------------------
    # Leave Measurement
    # ------------------------

    leave_unit = models.CharField(
        max_length=10,
        choices=LeaveUnit.choices,
        default=LeaveUnit.DAY,
        verbose_name=_("Leave Unit"),
        help_text=_("Defines whether leave is counted in days, hours, or minutes."),
    )

    allow_half_day = models.BooleanField(
        default=False,
        verbose_name=_("Allow Half Day"),
    )

    half_day_value = models.FloatField(
        default=0.5,
        verbose_name=_("Half Day Value"),
        help_text=_("Applicable only for day-based leaves."),
    )

    min_duration = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Minimum Duration"),
        help_text=_("Minimum duration allowed (based on leave unit)."),
    )

    max_duration = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Maximum Duration"),
        help_text=_("Maximum duration allowed (based on leave unit)."),
    )

    # ------------------------
    # Accrual & Expiry
    # ------------------------

    accrual_period = models.CharField(
        max_length=10,
        choices=LeaveAccrualPeriod.choices,
        default=LeaveAccrualPeriod.YEARLY,
        verbose_name=_("Accrual Period"),
    )

    accrual_quantity = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Accrual Quantity"),
        help_text=_("Leave allocated per accrual period."),
    )

    expiry_policy = models.CharField(
        max_length=15,
        choices=LeaveExpiryPolicy.choices,
        default=LeaveExpiryPolicy.NONE,
        verbose_name=_("Expiry Policy"),
    )

    allow_carry_forward = models.BooleanField(
        default=False,
        verbose_name=_("Allow Carry Forward"),
    )

    max_carry_forward = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Max Carry Forward"),
    )

    must_apply_within_accrual_period = models.BooleanField(
        default=False,
        verbose_name=_("Must Apply Within Same Period"),
        help_text=_(
            "If enabled, leave must be applied within the same accrual period "
            "(e.g. short leave must be used in the same month)."
        ),
    )

    # ------------------------
    # Existing Limits
    # ------------------------

    default_allocation = models.FloatField(blank=True, null=True)
    min_notice_days = models.FloatField(blank=True, null=True)
    max_days_limit = models.FloatField(blank=True, null=True)
    min_days_limit = models.FloatField(blank=True, null=True)
    allowed_days_per_year = models.FloatField(blank=True, null=True)

    leave_fy_start = models.DateField(blank=True, null=True)
    leave_fy_end = models.DateField(blank=True, null=True)

    color_hex = models.CharField(max_length=7, blank=True, null=True)
    text_color_hex = models.CharField(max_length=7, blank=True, null=True)

    # ------------------------
    # Restrictions
    # ------------------------

    consecutive_restriction = models.BooleanField(default=False)

    restricted_after_leave_types = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="restricted_by_leave_types",
    )

    # ------------------------
    # Audit Fields
    # ------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leave_types",
    )

    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_leave_types",
    )

    # =========================
    # VALIDATIONS
    # =========================

    def clean(self):
        # Half day only for day-based leaves
        if self.allow_half_day and self.leave_unit != LeaveUnit.DAY:
            raise ValidationError(_("Half day is only allowed for day-based leaves."))

        # Duration validation
        if self.min_duration and self.max_duration:
            if self.min_duration > self.max_duration:
                raise ValidationError(_("Minimum duration cannot exceed maximum."))

        # Accrual validation
        if self.accrual_period != LeaveAccrualPeriod.NONE and not self.accrual_quantity:
            raise ValidationError(_("Accrual quantity is required."))

        # Carry forward validation
        if not self.allow_carry_forward and self.max_carry_forward:
            raise ValidationError(_("Carry forward is disabled."))

        # Short leave rules
        if self.leave_unit in [LeaveUnit.HOUR, LeaveUnit.MINUTE]:
            if self.allow_half_day:
                raise ValidationError(_("Half day not applicable for short leaves."))
            if self.allow_carry_forward:
                raise ValidationError(_("Short leave cannot be carried forward."))

    # =========================
    # META
    # =========================

    def __str__(self):
        return self.leave_type

    class Meta:
        db_table = "tbl_leave_type"
        verbose_name = _("Leave Type")
        verbose_name_plural = _("Leave Types")


class LeaveStatusPermission(models.Model):
    role = models.CharField(max_length=100, blank=True, null=True, verbose_name="Role")
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="User",
    )
    leave_type= models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Leave Type",
    )
    status = models.CharField(
        max_length=30,
        choices=settings.LEAVE_STATUS_CHOICES,
        verbose_name="Leave Status",
    )

    class Meta:
        unique_together = ("role", "user", "status")
        verbose_name = "Leave Status Permission"
        verbose_name_plural = "Leave Status Permissions"

    def __str__(self):
        if self.user:
            return f"{self.user} -> {self.status}"
        return f"{self.role} -> {self.status}"

class LeaveBalanceOpenings(models.Model):
    """
    Unified Leave Balance Model

    - Yearly leave → month = None
    - Monthly leave → month = 1-12
    """

    # ----------------------------------
    # Core Relations
    # ----------------------------------

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="leave_balances",
    )

    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name="leave_balances",
    )

    # ----------------------------------
    # Period Definition
    # ----------------------------------

    year = models.PositiveIntegerField(
        default=_current_year,
    )

    month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Required only for monthly accrued leaves (1-12).",
    )

    # ----------------------------------
    # Balance Fields
    # ----------------------------------
    no_of_leaves = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Number of Leaves"),
        help_text=_( "The total number of leaves allocated to the user for this leave type." ), 
        )
    opening_balance = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    allocated = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total allocated for this period.",
    )

    used = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    remaining_leave_balances = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    closing_balance = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    # ----------------------------------
    # Audit Fields
    # ----------------------------------

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_leave_balances",
    )

    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_leave_balances",
    )

    # ----------------------------------
    # Meta
    # ----------------------------------

    class Meta:
        db_table = "tbl_leave_balance_openings"
        verbose_name = "Leave Balance"
        verbose_name_plural = "Leave Balances"
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "leave_type", "year", "month"],
                name="unique_leave_balance_period"
            )
        ]

    # ----------------------------------
    # String
    # ----------------------------------

    def __str__(self):
        period = f"{self.year}-{self.month}" if self.month else f"{self.year}"
        return f"{self.user} | {self.leave_type} | {period} | Remaining: {self.remaining_leave_balances}"

    # ----------------------------------
    # Validations
    # ----------------------------------

    def clean(self):
        """
        Enforce correct period behavior based on accrual type.
        """
        if self.leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY:
            if not self.month:
                raise ValidationError("Month is required for monthly leave.")
        else:
            if self.month:
                raise ValidationError("Month must be empty for yearly leave.")

    # ----------------------------------
    # Business Logic
    # ----------------------------------

    def can_apply_leave(self) -> bool:
        return self.is_active and self.remaining_leave_balances > 0

    def deduct_leave(self, days: float):
        """
        Safe deduction logic (should be wrapped in transaction.atomic externally)
        """
        if self.remaining_leave_balances < days:
            raise ValidationError("Insufficient leave balance.")

        self.used += days
        self.remaining_leave_balances -= days
        self.closing_balance = self.remaining_leave_balances
        self.save(update_fields=["used", "remaining_leave_balances", "closing_balance"])

    def add_accrual(self, quantity: float):
        """
        Add leave allocation (monthly or yearly accrual).
        """
        self.allocated += quantity
        self.opening_balance += quantity
        self.remaining_leave_balances += quantity
        self.closing_balance = self.remaining_leave_balances
        self.save(update_fields=[
            "allocated",
            "opening_balance",
            "remaining_leave_balances",
            "closing_balance",
        ])

    # ----------------------------------
    # Class Methods
    # ----------------------------------

    @classmethod
    def get_balance_for_date(cls, user, leave_type, leave_date):
        """
        Automatically resolve correct balance record
        based on leave date.
        """
        year = leave_date.year

        if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY:
            month = leave_date.month
        else:
            month = None

        return cls.objects.select_for_update().get(
            user=user,
            leave_type=leave_type,
            year=year,
            month=month,
        )


class LeaveTransaction(models.Model):
    leave_balance = models.ForeignKey(
        LeaveBalanceOpenings,
        on_delete=models.CASCADE,
        verbose_name=_("Leave Balance"),
        help_text=_("The leave balance associated with this transaction."),
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        verbose_name=_("Leave Type"),
        help_text=_("The type of leave being requested (e.g., sick leave, vacation)."),
        blank=True,null=True
    )
    transaction_date = models.DateField(
        default=timezone.now,
        verbose_name=_("Transaction Date"),
        help_text=_("The date when the leave transaction is recorded."),
    )
    no_of_days_applied = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name=_("Number of Days Applied"),
        help_text=_("Number of leave days applied for in this transaction."),
        blank=True,null=True
    )
    no_of_days_approved = models.FloatField(
        validators=[MinValueValidator(0)],
        default=0,
        verbose_name=_("Number of Days Approved"),
        help_text=_("Number of leave days that have been approved."),
        blank=True,null=True
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=[('add', 'Add'), ('subtract', 'Subtract')],
        verbose_name=_("Transaction Type"),
        help_text=_("The type of transaction (add or subtract leaves)."),
        blank=True,null=True
    )
    remarks = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Remarks"),
        help_text=_("Any additional remarks regarding the leave transaction."),
    )

    def __str__(self):
        return f"Leave Transaction for {self.leave_balance.user.username} - {self.leave_type.leave_type} on {self.transaction_date}"

    class Meta:
        db_table = "tbl_leave_transaction"
        managed = True
        verbose_name = _("Leave Transaction")
        verbose_name_plural = _("Leave Transactions")
        ordering = ["-transaction_date"]


