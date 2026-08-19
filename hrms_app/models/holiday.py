from datetime import time

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model


class Holiday(models.Model):
    title = models.CharField(max_length=100, verbose_name=_("Title"))
    short_code = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Short Code")
    )
    start_date = models.DateField(blank=True, null=True, verbose_name=_("Start Date"))
    end_date = models.DateField(blank=True, null=True, verbose_name=_("End Date"))
    desc = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    color_hex = models.CharField(
        max_length=7, blank=True, null=True, verbose_name=_("Color Hex Code")
    )
    
    # NEW FIELD: Make holidays user-specific
    applicable_users = models.ManyToManyField(
        get_user_model(),
        related_name="applicable_holidays",
        blank=True,
        verbose_name=_("Applicable Users"),
        help_text=_("Leave blank to apply to all users")
    )
    
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        related_name="created_holidays",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    updated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        related_name="updated_holidays",
        null=True,
        blank=True,
        verbose_name=_("Updated By"),
    )
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Year"))

    def save(self, *args, **kwargs):
        created_by = kwargs.pop("created_by", None)
        updated_by = kwargs.pop("updated_by", None)
        if not self.pk and created_by:
            self.created_by = created_by
        if updated_by:
            self.updated_by = updated_by
        super(Holiday, self).save(*args, **kwargs)

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("End date must be after start date."))

    def __str__(self):
        return f"{self.title} - {self.start_date}"

    class Meta:
        db_table = "tbl_holidays"
        managed = True
        verbose_name = _("Holiday")
        verbose_name_plural = _("Holidays")
        indexes = [
            models.Index(fields=["start_date"]),
            models.Index(fields=["end_date"]),
        ]

class WishingCard(models.Model):
    JobAnniversaryCard = _("Job Anniversary")
    BirthdayCard = _("Birthday")
    MarriageAnniversaryCard = ("Marriage Anniversary")
    
    Card_TYPES = [
        (JobAnniversaryCard,JobAnniversaryCard ),
        (BirthdayCard, BirthdayCard),
        (MarriageAnniversaryCard, MarriageAnniversaryCard),
    ]
    type = models.CharField(max_length=100, choices=Card_TYPES, blank=True, null=True, verbose_name=_('Card Type'))
    image = models.ImageField(upload_to='wishing_images/', blank=True, null=True, verbose_name=_('Image'))
    created_at = models.DateField(auto_now_add=True,blank=True, null=True)
    
    def __str__(self):
        return f'{self.type} - {self.image}'
    
    class Meta:
        db_table = 'tbl_wishing_card'
        verbose_name = _('Wishing Card')
        verbose_name_plural = _('Wishing Cards')


class HRAnnouncement(models.Model):
    class AnnouncementType(models.TextChoices):
        GENERAL = 'general', _('General')
        POLICY = 'policy', _('Policy Update')
        EVENT = 'event', _('Event')
        HOLIDAY = 'holiday', _('Holiday Notice')
        ALERT = 'alert', _('Urgent/Alert')

    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
        help_text=_("Short and clear title of the announcement.")
    )

    content = models.TextField(
        verbose_name=_("Content"),
        help_text=_("Full description or body of the announcement.")
    )

    type = models.CharField(
        max_length=20,
        choices=AnnouncementType.choices,
        default=AnnouncementType.GENERAL,
        verbose_name=_("Type"),
        help_text=_("Category/type of the announcement for filtering.")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Updated")
    )

    start_date = models.DateField(
        default=timezone.now,
        verbose_name=_("Start Date"),
        help_text=_("Date from which the announcement becomes visible.")
    )

    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("End Date"),
        help_text=_("Date after which the announcement is no longer shown. Leave blank for indefinite.")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Only active announcements will be shown to users.")
    )

    audience_roles = models.ManyToManyField(
        'auth.Group',
        blank=True,
        verbose_name=_("Audience Roles"),
        help_text=_("Limit visibility to specific user groups/roles.")
    )

    pinned = models.BooleanField(
        default=False,
        verbose_name=_("Pin Announcement"),
        help_text=_("Pinned announcements appear at the top.")
    )

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': _("End date cannot be earlier than start date.")})

    def is_visible(self):
        """Return True if the announcement is active and within the date range."""
        today = timezone.now().date()
        return (
            self.is_active and
            self.start_date <= today and
            (self.end_date is None or today <= self.end_date)
        )

    def short_content(self, length=100):
        """Return a shortened version of content for previews."""
        return (self.content[:length] + '...') if len(self.content) > length else self.content

    def __str__(self):
        return f"{self.title} ({self.get_type_display()})"

    class Meta:
        db_table = "tbl_announcement"
        verbose_name = _("HR Announcement")
        verbose_name_plural = _("HR Announcements")
        ordering = ['-pinned', '-start_date', '-created_at']


class OfficeClosure(models.Model):
    """
    Represents days when the office is closed (full day or partial).
    """
    FULL_DAY = 'full'
    HALF_DAY = 'half'
    CUSTOM = 'custom'

    CLOSURE_TYPE_CHOICES = [
        (FULL_DAY, 'Full Day'),
        (HALF_DAY, 'Half Day'),
        (CUSTOM, 'Custom'),
    ]

    date = models.DateField(
        unique=True,
        verbose_name="Closure Date",
        help_text="Date when the office was closed"
    )
    closure_type = models.CharField(
        max_length=10,
        choices=CLOSURE_TYPE_CHOICES,
        verbose_name="Type of Closure",
        help_text="Was it a full-day, half-day (e.g., post-lunch), or custom closure?"
    )
    short_code = models.CharField(
        max_length=10,
        verbose_name="Short Cde",
        help_text="Used to denote the attendance",
        default="SR"
    )
    reason = models.TextField(
        verbose_name="Reason for Closure",
        help_text="Provide a short explanation for the closure"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
        help_text="Timestamp when this entry was created"
    )

    class Meta:
        db_table = 'tbl_office_closer'
        verbose_name = "Office Closure"
        verbose_name_plural = "Office Closures"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.get_closure_type_display()} - {self.reason[:30]}"

    def is_closed_after_time(self, check_time: time = time(13, 0)) -> bool:
        """
        Check if the office is considered closed after a given time.
        """
        if self.closure_type == self.FULL_DAY:
            return True
        elif self.closure_type == self.HALF_DAY and check_time >= time(13, 0):
            return True
        return False

    @classmethod
    def is_office_closed(cls, date: 'datetime.date', current_time: time = None) -> bool:
        """
        Class-level method to determine if office was closed on a date,
        and optionally if it was closed after a specific time.
        """
        try:
            closure = cls.objects.get(date=date)
            return closure.is_closed_after_time(current_time) if current_time else True
        except cls.DoesNotExist:
            return False


