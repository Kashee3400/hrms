from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model

from .core import CustomUser
from .organization import OfficeLocation


class DeviceInformation(models.Model):
    device_location = models.ForeignKey(
        OfficeLocation,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Device Location"),
        help_text=_(
            "Where this device is located. For ex: - MCC or Cluster office location"
        ),
    )
    from_date = models.DateTimeField(
        verbose_name=_("From Date"),
        help_text=_("Enter the start date and time for the transaction log."),
    )
    to_date = models.DateTimeField(
        verbose_name=_("To Date"),
        help_text=_("Enter the end date and time for the transaction log."),
    )
    serial_number = models.CharField(
        max_length=50,
        verbose_name=_("Serial Number"),
        help_text=_("Enter the device serial number."),
        unique=True,  # Ensure serial numbers are unique
    )
    username = models.CharField(
        max_length=30,
        verbose_name=_("Username"),
        help_text=_("Enter the API username for authentication."),
    )
    password = models.CharField(
        max_length=50,
        verbose_name=_("Password"),
        help_text=_("Enter the API password for authentication."),
    )
    api_link = models.URLField(
        max_length=200,  # Increase if necessary to accommodate long URLs
        verbose_name=_("API Link"),
        help_text=_("Enter the API link for the device."),
        default="http://1.22.197.176:99/iclock/WebAPIService.asmx",  # Default link can be modified if needed
    )
    include_seconds = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.serial_number} from {self.from_date} to {self.to_date}"

    class Meta:
        db_table = "tbl_device_information"  # Updated table name for clarity
        managed = True
        verbose_name = _("Device Information")
        verbose_name_plural = _("Device Information Records")


class AttendanceLog(models.Model):
    applied_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="attendance_log",
        verbose_name=_("Applied By"),
    )
    start_date = models.DateTimeField(
        verbose_name=_("Start Date"),
        help_text=_("The date and time when attendance starts."),
    )
    end_date = models.DateTimeField(
        verbose_name=_("End Date"),
        help_text=_("The date and time when attendance ends."),
    )
    from_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("From Date"),
        help_text=_(
            "Optional field for specifying a starting date for regularization."
        ),
    )
    to_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("To Date"),
        help_text=_("Optional field for specifying an ending date for regularization."),
    )
    reg_duration = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Regularization Duration"),
        help_text=_("Specify the duration for which regularization is requested."),
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
        help_text=_("A unique slug generated from the title, used for URL routing."),
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
        help_text=_("Enter a title for the attendance log."),
    )
    is_regularisation = models.BooleanField(
        default=False,
        verbose_name=_("Is Regularisation"),
        help_text=_("Indicate whether this entry is for regularization."),
    )
    duration = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("Duration"),
        help_text=_("Specify the duration of attendance."),
    )
    reg_status = models.CharField(
        max_length=20,
        choices=settings.ATTENDANCE_REGULARISED_STATUS_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Regularization Status"),
        help_text=_("The current status of the regularization request."),
    ) # late coming, early going, or mis punching
    status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=settings.ATTENDANCE_LOG_STATUS_CHOICES,
        verbose_name=_("Status"),
        help_text=_("Current status of the attendance log."),
    )  # pending, approved, etc
    att_status = models.CharField(
        max_length=20,
        choices=settings.ATTENDANCE_STATUS_CHOICES,
        verbose_name=_("Attendance Status"),
        help_text=_("Indicate the attendance status for this log entry."),
    )
    att_status_short_code = models.CharField(
        max_length=20,
        verbose_name=_("Short Code"),
        blank=True,
        null=True,
        help_text=_("A short code representing the attendance status."),
    ) # present, absent, or half-day
    color_hex = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        verbose_name=_("Color Hex Code"),
        help_text=_("Optional: Color code associated with this attendance entry."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        verbose_name=_("Updated By"),
        blank=True,
        null=True,
        help_text=_("User who last updated this attendance log entry."),
    )
    updated_at = models.DateTimeField(auto_now=True)
    reason = models.CharField(
        max_length=100,
        verbose_name=_("Reason"),
        blank=True,
        null=True,
        help_text=_("Reason for the attendance entry."),
    )
    is_submitted = models.BooleanField(
        default=False,
        verbose_name=_("Is Submitted"),
        help_text=_("Indicate if the regularization has been submitted."),
    )
    regularized = models.BooleanField(
        default=False,
        verbose_name=_("Attendance Regularized"),
        help_text=_("Indicate if this entry is for late coming regularization."),
    )
    is_early_going = models.BooleanField(
        default=False,
        verbose_name=_("Is Early Going"),
        help_text=_("Indicate if this entry is for early going regularization."),
    )
    regularized_backend = models.BooleanField(
        default=False,
        blank =True,
        null = True,
        verbose_name=_("Backend Regularized"),
        help_text=_("Indicate if this entry is regularized from backend."),
    )
    def clean(self):
        if self.reg_status != settings.MIS_PUNCHING:
            if self.start_date is not None and self.end_date is not None:
                if self.start_date >= self.end_date:
                    raise ValidationError(_("End date must be after start date."))
            if self.from_date and self.to_date and self.from_date >= self.to_date:
                raise ValidationError(_("To date must be after from date."))
        else:
            self.start_date = self.from_date
            self.end_date = self.to_date

    def save(self, *args, **kwargs):
        # Automatically generate slug if not provided
        if not self.slug:
            self.slug = slugify(self.title)
        super(AttendanceLog, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.title}"

    def approve(self, action_by, reason=None):
        self.save(
            update_fields=[
                "updated_at",
            ]
        )
        self.add_action(action=settings.APPROVED, performed_by=action_by, comment=reason)

    def reject(self, action_by, reason=None):
        self.status = settings.REJECTED
        self.save(update_fields=["status", "updated_at"])
        self.add_action(action=self.status, performed_by=action_by, comment=reason)

    def recommend(self, action_by, reason=None):
        self.status = settings.RECOMMEND
        self.save(update_fields=["status", "updated_at"])
        self.add_action(action=self.status, performed_by=action_by, comment=reason)

    def notrecommend(self, action_by, reason=None):
        self.status = settings.NOT_RECOMMEND
        self.save(update_fields=["status", "updated_at"])
        self.add_action(action=self.status, performed_by=action_by, comment=reason)

    class Meta:
        db_table = "tbl_events"
        managed = True
        verbose_name = _("Attendance Log")
        verbose_name_plural = _("Attendance Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["applied_by"]),
            models.Index(fields=["status"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["end_date"]),
        ]

    def add_action(self, action, performed_by, comment=None):
        AttendanceLogAction.create_log(
            self, action=action, action_by=performed_by, notes=comment
        )

class AttendanceLogHistory(models.Model):
    attendance_log = models.ForeignKey(AttendanceLog, on_delete=models.CASCADE, related_name='history')
    previous_data = models.JSONField()  # Store the old data
    modified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    modified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"History for {self.attendance_log} at {self.modified_at}"

    def revert(self):
        """
        Reverts the associated AttendanceLog to the state in previous_data.
        Handles foreign key relationships correctly by assigning the instances.
        """
        for field, value in self.previous_data.items():
            # If the field is a ForeignKey, assign the actual instance, not just the ID
            try:
                field_object = self.attendance_log._meta.get_field(field)
                if isinstance(field_object, models.ForeignKey):
                    # Assuming `value` is the ID, we need to get the related instance
                    related_model = field_object.related_model
                    if value is not None:
                        value = related_model.objects.get(id=value)  # Get the related instance
            except models.FieldDoesNotExist:
                pass  # Skip fields that do not exist on the model

            setattr(self.attendance_log, field, value)

        self.attendance_log.save()

    class Meta:
        verbose_name = "Attendance Log History"
        verbose_name_plural = "Attendance Log Histories"
        ordering = ['-modified_at']
        db_table = "attendance_log_history"
        indexes = [
            models.Index(fields=['attendance_log']),  # Index for faster queries on attendance_log
            models.Index(fields=['modified_at']),     # Index for filtering/sorting by modified_at
        ]
        permissions = [
            ("can_view_history", "Can view attendance log history"),
        ]


class AttendanceLogAction(models.Model):
    log = models.ForeignKey(
        AttendanceLog,
        on_delete=models.CASCADE,
        related_name="actions",
        verbose_name=_("Attendance Log"),
    )
    action_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, verbose_name=_("Action By")
    )
    action_by_name = models.CharField(max_length=255, verbose_name=_("Action By Name"))
    action_by_email = models.EmailField(verbose_name=_("Action By Email"))
    action = models.CharField(max_length=100, verbose_name=_("Action"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    @classmethod
    def create_log(cls, log, action_by, action, notes=""):
        cls.objects.create(
            log=log,
            action_by=action_by,
            action_by_name=f"{action_by.first_name} {action_by.last_name}",
            action_by_email=action_by.email,
            action=action,
            notes=notes,
        )

    def __str__(self):
        return f"{self.log.title} - {self.action} by {self.action_by}"

    class Meta:
        db_table = "tbl_attendance_log_actions"
        managed = True
        verbose_name = _("Attendance Log Action")
        verbose_name_plural = _("Attendance Log Actions")


class AttendanceSetting(models.Model):
    full_day_hours = models.PositiveIntegerField(
        default=8, verbose_name=_("Full Day Hours")
    )
    half_day_hours = models.PositiveIntegerField(
        default=4, verbose_name=_("Half Day Hours")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    def __str__(self):
        return f"{self.full_day_hours} {self.half_day_hours}"

    class Meta:
        db_table = "tbl_attendance_setting"
        managed = True
        verbose_name = _("Attendance Setting")
        verbose_name_plural = _("Attendance Settings")


class AttendanceStatusColor(models.Model):
    status = models.CharField(
        max_length=50,
        choices=settings.ATTENDANCE_STATUS_CHOICES,
        verbose_name=_("Status"),
    )
    color = models.CharField(max_length=20, verbose_name=_("Color"))
    color_hex = models.CharField(
        max_length=7, blank=True, null=True, verbose_name=_("Color Hex Code")
    )
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))

    def __str__(self):
        return f"{self.status} {self.color_hex}"

    class Meta:
        db_table = "tbl_attendance_status_color"
        managed = True
        verbose_name = _("Attendance Status Color")
        verbose_name_plural = _("Attendance Status Colors")


class OffDay(models.Model):
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField()
    off_type = models.CharField(
        max_length=50,
        choices=[
            ("Sunday", "Sunday"),
        ],
        default="Sunday",
    )
    reason = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("employee", "date")
        verbose_name = "Off Day"
        verbose_name_plural = "Off Days"

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.off_type}"


class LockStatus(models.Model):
    LOCK_CHOICES = (
        ('locked', _('Locked')),
        ('unlocked', _('Unlocked')),
    )

    is_locked = models.CharField(
        max_length=10,
        choices=LOCK_CHOICES,
        default='unlocked',
        verbose_name=_("Lock Status"),
        help_text=_("Determines whether certain models are locked for modifications."),
    )
    reason = models.TextField(null=True, blank=True, verbose_name=_("Lock Reason"), help_text=_("The reason for locking the actions."))
    locked_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Lock Timestamp"))
    from_date = models.DateField(blank=True,null=True,help_text=_("Provide the from date to lock the attendance"),verbose_name=_("From Date"))
    to_date = models.DateField(blank=True,null=True,help_text=_("Provide the to date to lock the attendance"),verbose_name=_("To Date"))
    lock_month = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Lock Month"))
    lock_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Lock Year"))
    
    def __str__(self):
        return f"Lock Status: {self.is_locked} - Reason: {self.reason or 'No reason provided'}"
    
    class Meta:
        verbose_name = _("Lock Status")
        verbose_name_plural = _("Lock Statuses")


class AttendanceCache(models.Model):
    """
    Pre-calculated attendance data cache for faster retrieval.
    
    This model stores processed attendance data to improve query performance
    for dashboard views and reporting functionality.
    """
    
    # Color hex validator
    hex_color_validator = RegexValidator(
        regex=r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$',
        message='Enter a valid hex color code (e.g., #FF0000 or #F00)'
    )
    
    employee = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name="Employee",
        help_text="The employee this attendance record belongs to",
        related_name="attendance_cache"
    )
    
    date = models.DateField(
        db_index=True,
        verbose_name="Date",
        help_text="The date for this attendance record"
    )
    
    status = models.CharField(
        max_length=10,
        verbose_name="Attendance Status",
        help_text="Current attendance status (present, absent, late, etc.)",
        db_index=True
    )
    
    color_hex = models.CharField(
        max_length=7,
        default="#000000",
        validators=[hex_color_validator],
        verbose_name="Status Color",
        help_text="Hex color code for UI display of this status"
    )
    
    # Additional metadata for flexibility
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Additional Metadata",
        help_text="Extra data stored as JSON for future extensions"
    )
    
    # Tracking fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
        help_text="When this cache record was first created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At",
        help_text="When this cache record was last modified"
    )

    class Meta:
        verbose_name = "Attendance Cache"
        verbose_name_plural = "Attendance Caches"
        
        # Database constraints
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'date'],
                name='unique_employee_date_attendance'
            ),
        ]
        
        # Optimized indexes for common query patterns
        indexes = [
            # Primary lookup pattern: employee + date range
            models.Index(
                fields=['employee', 'date'], 
                name='idx_attendance_emp_date'
            ),
            # Date range queries for reporting
            models.Index(
                fields=['date'], 
                name='idx_attendance_date'
            ),
            # Status filtering
            models.Index(
                fields=['status'], 
                name='idx_attendance_status'
            ),
            # Recent records lookup
            models.Index(
                fields=['created_at'], 
                name='idx_attendance_created'
            ),
            # Combined status + date for dashboard queries
            models.Index(
                fields=['status', 'date'], 
                name='idx_attendance_status_date'
            ),
        ]
        
        # Default ordering
        ordering = ['-date', 'employee__username']
        
        # Database table name
        db_table = 'attendance_cache'
    
    def __str__(self):
        return f"{self.employee.get_full_name() or self.employee.username} - {self.date} - {self.status}"
    
    def __repr__(self):
        return f"<AttendanceCache: {self.employee_id} on {self.date}>"


class AttendanceCacheLog(models.Model):
    """
    Track attendance cache processing logs and system operations.
    
    This model maintains an audit trail of all cache processing operations
    including performance metrics and error tracking.
    """
    
    PROCESS_TYPES = [
        ('daily', 'Daily Processing'),
        ('monthly', 'Monthly Recalculation'),
        ('manual', 'Manual Trigger'),
        ('correction', 'Data Correction'),
        ('bulk_import', 'Bulk Import'),
        ('system_sync', 'System Synchronization'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    process_type = models.CharField(
        max_length=20,
        choices=PROCESS_TYPES,
        verbose_name="Process Type",
        help_text="Type of cache processing operation",
        db_index=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Processing Status",
        help_text="Current status of the processing operation",
        db_index=True
    )
    
    start_date = models.DateField(
        verbose_name="Start Date",
        help_text="Beginning date of the processing period"
    )
    
    end_date = models.DateField(
        verbose_name="End Date",
        help_text="End date of the processing period"
    )
    
    # Processing metrics
    employees_processed = models.PositiveIntegerField(
        default=0,
        verbose_name="Employees Processed",
        help_text="Total number of employees processed in this operation"
    )
    
    records_created = models.PositiveIntegerField(
        default=0,
        verbose_name="Records Created",
        help_text="Number of new cache records created"
    )
    
    records_updated = models.PositiveIntegerField(
        default=0,
        verbose_name="Records Updated",
        help_text="Number of existing cache records updated"
    )
    
    processing_time_seconds = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Processing Time (seconds)",
        help_text="Total time taken for processing in seconds"
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        verbose_name="Error Message",
        help_text="Detailed error message if processing failed"
    )
    
    error_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Error Count",
        help_text="Number of errors encountered during processing"
    )
    
    # Additional context
    triggered_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Triggered By",
        help_text="User or system that initiated this process"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Processing Notes",
        help_text="Additional notes or context about this processing run"
    )
    
    # Timestamps
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Started At",
        help_text="When this processing operation began"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completed At",
        help_text="When this processing operation finished"
    )

    class Meta:
        verbose_name = "Attendance Cache Log"
        verbose_name_plural = "Attendance Cache Logs"
        
        # Optimized indexes for common queries
        indexes = [
            # Status monitoring queries
            models.Index(
                fields=['status', 'started_at'], 
                name='idx_cache_log_status_started'
            ),
            # Process type analysis
            models.Index(
                fields=['process_type', 'status'], 
                name='idx_cache_log_type_status'
            ),
            # Date range processing history
            models.Index(
                fields=['start_date', 'end_date'], 
                name='idx_cache_log_date_range'
            ),
            # Performance monitoring
            models.Index(
                fields=['processing_time_seconds'], 
                name='idx_cache_log_processing_time'
            ),
            # Recent activity lookup
            models.Index(
                fields=['started_at'], 
                name='idx_cache_log_started'
            ),
        ]
        
        # Default ordering - most recent first
        ordering = ['-started_at']
        
        # Database table name
        db_table = 'attendance_cache_log'
    
    def __str__(self):
        return f"{self.get_process_type_display()} - {self.get_status_display()} ({self.started_at.date()})"
    
    def __repr__(self):
        return f"<AttendanceCacheLog: {self.process_type} {self.status}>"
    
    @property
    def duration(self):
        """Calculate processing duration if completed."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def is_completed(self):
        """Check if processing is completed (success or failure)."""
        return self.status in ['completed', 'failed', 'cancelled']
    
    @property
    def success_rate(self):
        """Calculate success rate based on records processed vs errors."""
        total_records = self.records_created + self.records_updated
        if total_records == 0:
            return 0
