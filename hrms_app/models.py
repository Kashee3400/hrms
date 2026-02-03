from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import random
import string
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from datetime import timedelta,time
import uuid
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.templatetags.static import static
from .manager.leave_days import LeaveDayManager


class Role(models.Model):
    name = models.CharField(
        max_length=50,
        choices=settings.ROLE_CHOICES,
        verbose_name=_("Role Name"),
        help_text=_("Select a role for the user. This field is required."),
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_("Optional: Provide a brief description of the role."),
    )

    def __str__(self):
        return self.get_name_display()

    class Meta:
        db_table = "tbl_role"
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_role_name")
        ]


class CustomUser(AbstractUser):
    official_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Official E-mail"),
        help_text=_("Optional: Enter the user's official email address."),
    )
    is_rm = models.BooleanField(
        default=False,
        verbose_name=_("Is Manager"),
        help_text=_("Indicates whether the user is a manager."),
    )
    reports_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Reports To"),
        help_text=_("Select the manager this user reports to."),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Role"),
        help_text=_("Select a role for the user."),
    )
    device_location = models.ForeignKey(
        "OfficeLocation",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Device Location"),
        help_text=_(
            "Specify the location where this device is located. Example: MCC or Cluster office location."
        ),
    )
    is_personal_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.get_full_name()

    def toggle_manager_status(self):
        self.is_rm = not self.is_rm
        self.save()

    class Meta:
        db_table = "tbl_user"
        managed = True
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["username"]


class Logo(models.Model):
    logo = models.CharField(
        max_length=100,
        verbose_name=_("Logo"),
        help_text=_("Provide the name of the logo."),
    )
    logo_image = models.ImageField(
        upload_to="logos/",
        blank=True,
        null=True,
        verbose_name=_("Logo Image"),
        help_text=_("Optional: Upload an image for the logo."),
    )

    def __str__(self):
        return f"{self.logo} - {self.logo_image}"

    class Meta:
        db_table = "tbl_logo"
        managed = True
        verbose_name = _("Logo")
        verbose_name_plural = _("Logos")
        ordering = ["logo"]


class Department(models.Model):
    department = models.CharField(
        max_length=100,
        verbose_name=_("Department"),
        help_text=_("Enter the name of the department."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether the department is active."),
    )
    slug = models.SlugField(
        unique=True,
        max_length=100,
        verbose_name=_("Slug"),
        help_text=_(
            "Unique slug for the department. Automatically generated if left blank."
        ),
    )
    created_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when the department was created."),
    )
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when the department was last updated."),
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="department_updated_by",
        null=True,
        verbose_name=_("Created By"),
        help_text=_("The user who created this department."),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="department_created_by",
        null=True,
        verbose_name=_("Updated By"),
        help_text=_("The user who last updated this department."),
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text=_("Optional: Provide a description of the department."),
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.department)
        super(Department, self).save(*args, **kwargs)

    def __str__(self):
        return self.department

    class Meta:
        db_table = "tbl_department"
        managed = True
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        ordering = ["department"]
        constraints = [
            models.UniqueConstraint(
                fields=["department"], name="unique_department_name"
            )
        ]


class Designation(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        verbose_name=_("Department"),
        help_text=_("Select the department for this designation."),
    )
    slug = models.SlugField(
        unique=True,
        max_length=100,
        verbose_name=_("Slug"),
        help_text=_(
            "Unique slug for the designation. Automatically generated if left blank."
        ),
    )
    designation = models.CharField(
        max_length=100,
        verbose_name=_("Designation"),
        help_text=_("Enter the name of the designation."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether the designation is active."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when the designation was created."),
    )
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when the designation was last updated."),
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="designation_created_by",
        verbose_name=_("Created By"),
        help_text=_("The user who created this designation."),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="designation_updated_by",
        verbose_name=_("Updated By"),
        help_text=_("The user who last updated this designation."),
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text=_("Optional: Provide a description of the designation."),
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.designation)
        super(Designation, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.designation}"

    class Meta:
        db_table = "tbl_designation"
        managed = True
        verbose_name = _("Designation")
        verbose_name_plural = _("Designations")
        ordering = ["designation"]
        constraints = [
            models.UniqueConstraint(
                fields=["designation"], name="unique_designation_name"
            )
        ]


class Gender(models.Model):
    gender = models.CharField(
        max_length=30,
        verbose_name=_("Gender"),
        help_text=_("Enter the gender value (e.g., Male, Female, etc.)."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether the gender is active."),
    )
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when this record was last updated."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="gender_created_by",
        verbose_name=_("Created By"),
        help_text=_("The user who created this record."),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="gender_updated_by",
        verbose_name=_("Updated By"),
        help_text=_("The user who last updated this record."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )

    def __str__(self):
        return f"{self.gender}"

    def save(self, *args, **kwargs):
        if self.pk:
            if hasattr(self, "_updated_by"):
                self.updated_by = self._updated_by
        elif hasattr(self, "_created_by"):
            self.created_by = self._created_by
        super(Gender, self).save(*args, **kwargs)

    class Meta:
        db_table = "tbl_gender"
        managed = True
        verbose_name = _("Gender")
        verbose_name_plural = _("Genders")
        indexes = [
            models.Index(fields=["gender"], name="idx_gender_gender"),
        ]


class MaritalStatus(models.Model):
    marital_status = models.CharField(
        max_length=30,
        verbose_name=_("Marital Status"),
        help_text=_("Enter the marital status value (e.g., Single, Married, etc.)."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether the marital status is active."),
    )
    created_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )

    def __str__(self):
        return f"{self.marital_status}"

    class Meta:
        db_table = "tbl_marital_status"
        managed = True
        verbose_name = _("Marital Status")
        verbose_name_plural = _("Marital Statuses")
        indexes = [
            models.Index(fields=["marital_status"], name="idx_marital_status"),
        ]


class PermanentAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="permanent_addresses",
        verbose_name=_("Employee"),
        blank=True,
        null=True,
        help_text=_("Select the employee to associate with this permanent address."),
    )
    address_line_1 = models.CharField(
        max_length=100,
        verbose_name=_("Address Line 1"),
        help_text=_("Enter the first line of the address."),
    )
    address_line_2 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Address Line 2"),
        help_text=_("Optional: Enter the second line of the address."),
    )
    country = models.CharField(
        max_length=50,
        verbose_name=_("Country"),
        help_text=_("Enter the country for this address."),
    )
    district = models.CharField(
        max_length=50,
        verbose_name=_("District"),
        help_text=_("Enter the district for this address."),
    )
    state = models.CharField(
        max_length=50,
        verbose_name=_("State"),
        help_text=_("Enter the state for this address."),
    )
    zipcode = models.CharField(
        max_length=10,
        verbose_name=_("ZIP Code"),
        help_text=_("Enter the postal code for this address."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether this address is active."),
    )
    created_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )

    def __str__(self):
        return f"{self.user.get_full_name()} {self.address_line_1}, {self.state}, {self.zipcode}"

    class Meta:
        db_table = "tbl_permanent_address"
        managed = True
        verbose_name = _("Permanent Address")
        verbose_name_plural = _("Permanent Addresses")
        indexes = [
            models.Index(fields=["zipcode"], name="idx_permanent_zipcode"),
        ]


class CorrespondingAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="corres_addresses",
        verbose_name=_("Employee"),
        blank=True,
        null=True,
        help_text=_(
            "Select the employee to associate with this corresponding address."
        ),
    )
    address_line_1 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Address Line 1"),
        help_text=_("Optional: Enter the first line of the address."),
    )
    address_line_2 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Address Line 2"),
        help_text=_("Optional: Enter the second line of the address."),
    )
    country = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Country"),
        help_text=_("Optional: Enter the country for this address."),
    )
    district = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("District"),
        help_text=_("Optional: Enter the district for this address."),
    )
    state = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("State"),
        help_text=_("Optional: Enter the state for this address."),
    )
    zipcode = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_("ZIP Code"),
        help_text=_("Optional: Enter the postal code for this address."),
    )

    def __str__(self):
        return f"{self.user.get_full_name()} {self.address_line_1}, {self.state}, {self.zipcode}"

    class Meta:
        db_table = "tbl_correspondence_address"
        managed = True
        verbose_name = _("Corresponding Address")
        verbose_name_plural = _("Corresponding Addresses")
        indexes = [
            models.Index(fields=["zipcode"], name="idx_corresponding_zipcode"),
        ]


class Religion(models.Model):
    religion = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Religion"),
        help_text=_("Enter the religion (e.g., Christianity, Islam, Hinduism, etc.)."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether this religion is active."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )

    def __str__(self):
        return self.religion

    class Meta:
        db_table = "tbl_religion"
        managed = True
        verbose_name = _("Religion")
        verbose_name_plural = _("Religions")
        indexes = [
            models.Index(fields=["religion"], name="idx_religion"),
        ]


class Family(models.Model):
    EMPLOYEE_RELATIONSHIP_CHOICES = [
        ("Spouse", "Spouse"),
        ("Child", "Child"),
        ("Parent", "Parent"),
        ("Sibling", "Sibling"),
        ("Other", "Other"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="families",
        verbose_name=_("Employee"),
        help_text=_("Select the employee associated with this family member."),
    )
    member_name = models.CharField(
        max_length=100,
        verbose_name=_("Member Name"),
        help_text=_("Enter the name of the family member."),
    )
    relationship = models.CharField(
        max_length=20,
        choices=EMPLOYEE_RELATIONSHIP_CHOICES,
        verbose_name=_("Relationship"),
        help_text=_("Select the relationship of the family member to the employee."),
    )
    contact_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name=_("Contact Number"),
        help_text=_("Enter the contact number of the family member (optional)."),
    )

    def __str__(self):
        return f"{self.member_name} ({self.relationship}) - {self.user}"

    class Meta:
        db_table = "tbl_family_details"
        managed = True
        verbose_name = _("Family Detail")
        verbose_name_plural = _("Family Details")
        indexes = [
            models.Index(fields=["relationship"], name="idx_family_relationship"),
        ]


class PersonalDetails(models.Model):

    salutation = models.CharField(
        max_length=10,
        choices=settings.SALUTATION_CHOICES,
        default="Mr.",
        verbose_name=_("Salutation"),
        help_text=_("Select the salutation for the employee."),
    )
    employee_code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Employee Code"),
        help_text=_("Enter the employee code with company short code prefix."),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        default=0,
        on_delete=models.CASCADE,
        related_name="personal_detail",
        verbose_name=_("Employee"),
    )
    avatar = models.FileField(
        upload_to="avatar/",
        blank=True,
        null=True,
        verbose_name=_("Avatar"),
        help_text=_("Upload a profile picture for the employee."),
    )
    mobile_number = models.CharField(
        max_length=15,
        unique=True,
        verbose_name=_("Mobile Number"),
        help_text=_("Enter the employee's personal mobile number."),
    )
    alt_mobile_number = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_("Emergency Contact Number"),
        help_text=_("Enter an alternate mobile number for the employee (optional)."),
    )
    cug_mobile_number = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_("Company Mobile Number"),
        help_text=_("Enter the company's mobile number for the employee (optional)."),
    )
    gender = models.ForeignKey(
        "Gender",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Gender"),
        help_text=_("Select the employee's gender."),
    )
    designation = models.ForeignKey(
        "Designation",
        on_delete=models.CASCADE,
        verbose_name=_("Designation"),
        help_text=_("Select the employee's designation."),
    )
    official_mobile_number = models.CharField(
        max_length=15,
        unique=True,
        verbose_name=_("Official Mobile Number"),
        help_text=_("Enter the employee's official mobile number."),
    )
    religion = models.ForeignKey(
        Religion,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Religion"),
        help_text=_("Select the employee's religion (optional)."),
    )
    marital_status = models.ForeignKey(
        "MaritalStatus",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Marital Status"),
        help_text=_("Select the employee's marital status (optional)."),
    )
    birthday = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Birthday"),
        help_text=_("Enter the employee's birthday (optional)."),
    )
    marriage_ann = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Marriage Anniversary"),
        help_text=_("Enter the employee's marriage anniversary (optional)."),
    )

    doj = models.DateField(
        verbose_name=_("Date of Joining"),
        help_text=_("Enter the employee's date of joining."),
    )
    dol = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of Leaving"),
        help_text=_("Enter the employee's date of leaving (if applicable)."),
    )
    dor = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of Resignation"),
        help_text=_("Enter the employee's date of resignation (if applicable)."),
    )
    dot = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of Transfer"),
        help_text=_(
            "Enter the employee's date of transfer (if transferred to other location)."
        ),
    )
    dof = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of Final Settlement"),
        help_text=_("Enter the employee's final settlement date (if applicable)."),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when this record was last updated."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pd_created_by",
        verbose_name=_("Created By"),
        help_text=_("The user who created this record."),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pd_updated_by",
        verbose_name=_("Updated By"),
        help_text=_("The user who last updated this record."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this record was created."),
    )

    def __str__(self):
        return f"Personal Details of {self.user.first_name} - {self.mobile_number}"
    
    @property
    def avatar_url(self):
        try:
            if self.avatar and self.avatar.name:
                return self.avatar.url
        except Exception:
            pass
        return static("images/faces/face8.jpg")

    def get_avatar_url(self):
        return self.avatar_url
    
    class Meta:
        db_table = "tbl_personal_details"
        managed = True
        verbose_name = _("Personal Detail")
        verbose_name_plural = _("Personal Details")
        indexes = [
            models.Index(fields=["employee_code"], name="idx_employee_code"),
        ]


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


class BankDetails(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        help_text=_("Select the user associated with these bank details."),
    )
    account_number = models.CharField(
        max_length=50,
        verbose_name=_("Account Number"),
        help_text=_("Enter the bank account number."),
    )
    bank_name = models.CharField(
        max_length=100,
        verbose_name=_("Bank Name"),
        help_text=_("Enter the name of the bank."),
    )
    branch_name = models.CharField(
        max_length=100,
        verbose_name=_("Branch Name"),
        help_text=_("Enter the name of the bank branch."),
    )
    ifsc_code = models.CharField(
        max_length=20,
        verbose_name=_("IFSC Code"),
        help_text=_("Enter the IFSC code of the bank."),
    )
    pan_number = models.CharField(
        max_length=10,
        verbose_name=_("PAN Number"),
        help_text=_("Enter the PAN number of the user."),
    )

    class Meta:
        db_table = "tbl_bank_detail"
        managed = True
        verbose_name = _("Bank Detail")
        verbose_name_plural = _("Bank Details")
        indexes = [
            models.Index(fields=["user", "account_number"], name="idx_user_account"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account_number"], name="unique_user_account"
            ),
        ]

    def __str__(self):
        return f"Bank Details of {self.user.first_name} - {self.bank_name}, {self.IFSC_code}, {self.branch_name}"

    def clean(self):
        if len(self.pan_number) != 10:
            raise ValidationError(_("PAN number must be exactly 10 characters long."))


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
    applyingDate = models.DateTimeField(auto_now=True, verbose_name=_("Applying Date"))
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

class OfficeLocation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Unique Identifier",
        help_text="Unique ID for this location, generated automatically.",
    )
    location_name = models.CharField(
        max_length=100,
        verbose_name="Location Name",
        help_text="Enter the name of the location (e.g., Head Office, Cluster Office, etc.)",
    )
    office_type = models.CharField(
        max_length=50,
        choices=settings.OFFICE_TYPE_CHOICES,
        verbose_name="Office Type",
        help_text="Specify the type of office (Head Office, Cluster Office, MCC, BMC, MPP).",
    )
    address = models.TextField(
        verbose_name="Address", help_text="Enter the complete address of the location."
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="Latitude",
        help_text="Enter the latitude of the location.",
        blank=True,
        null=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="Longitude",
        help_text="Enter the longitude of the location.",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Created At",
        help_text="The date and time when this record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Updated At",
        help_text="The date and time when this record was last updated.",
    )
    created_by = models.ForeignKey(
        CustomUser,
        related_name="location_created_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Created By",
        help_text="The user who created this record.",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        related_name="location_updated_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Updated By",
        help_text="The user who last updated this record.",
    )

    class Meta:
        verbose_name = "Office Location"
        verbose_name_plural = "Office Locations"
        ordering = ["location_name"]

    def __str__(self):
        return f"{self.location_name} ({self.office_type})"

    def save(self, *args, **kwargs):
        """
        Override the save method to include custom logic for automatically populating
        `created_by` and `updated_by` fields based on the authenticated user.
        """
        # Expecting 'user' to be passed in kwargs when calling save()
        user = kwargs.pop("user", None)
        if user:
            if not self.pk:  # If the object is being created
                self.created_by = user
            self.updated_by = user  # Always set updated_by

        super(OfficeLocation, self).save(*args, **kwargs)


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

from .choices.leave import LeaveUnit,LeaveAccrualPeriod,LeaveExpiryPolicy
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

from django.core.validators import MinValueValidator, MaxValueValidator

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
        default=timezone.now().year,
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


class CompensatoryOff(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, verbose_name="Unique ID")

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
    
    
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        related_name="created_holidays",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
    )
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))
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
        if not self.pk:
            self.created_by = kwargs.pop("created_by", None)
        self.updated_by = kwargs.pop("updated_by", None)
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

        # Call the parent class's save method to save the object
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

    def extend(self, action_by, new_end_date, new_end_time, reason=None):
        self.extended_end_date = new_end_date
        self.extended_end_time = new_end_time
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
            comments=f"Tour extended to {new_end_date} {new_end_time}. Reason: {reason}",
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
        if not self.pk:
            self.created_by = kwargs.pop("created_by", None)
        self.updated_by = kwargs.pop("updated_by", None)
        super(Bill, self).save(*args, **kwargs)

    def __str__(self):
        return f"Bill {self.id} for Tour {self.tour.id}"

    class Meta:
        db_table = "tbl_tour_bill"
        managed = True
        verbose_name = _("Tour Bill")
        verbose_name_plural = _("Tour Bills")

# models.py
from django.db import models

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
    created_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
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

    def __str__(self):
        return f"{self.action} by {self.action_by_name} on {self.timestamp}"

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
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))

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
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(
        auto_now_add=True, blank=True, null=True, verbose_name=_("Updated At")
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
    sent_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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
        unique_together = ("email", "otp")

    def __str__(self):
        return f"OTP for {self.email} ({'verified' if self.verified else 'pending'})"

    def is_expired(self, expiry_minutes=10):
        """
        Check if the OTP is expired based on the expiry time.
        """
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expiry_minutes)
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


from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


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
        return ((total_records - self.error_count) / total_records) * 100