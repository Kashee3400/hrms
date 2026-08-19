import uuid

from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .core import CustomUser


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
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when the department was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when the department was last updated."),
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="department_created_by",
        null=True,
        verbose_name=_("Created By"),
        help_text=_("The user who created this department."),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="department_updated_by",
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
        auto_now=True,
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
        auto_now_add=True,
        verbose_name="Created At",
        help_text="The date and time when this record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
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


