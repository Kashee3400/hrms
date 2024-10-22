from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import AbstractUser
from django.db import models
import random
from django.template.defaultfilters import filesizeformat
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.timesince import timesince
import random
import string
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import transaction, IntegrityError


class Role(models.Model):
    name = models.CharField(max_length=50, choices=settings.ROLE_CHOICES, verbose_name=_("Role Name"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    
    def __str__(self):
        return self.get_name_display()

    class Meta:
        db_table = "tbl_role"
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")


class CustomUser(AbstractUser):
    official_email = models.EmailField(
        blank=True, null=True, verbose_name=_("Official E-mail")
    )
    is_rm = models.BooleanField(default=False, verbose_name=_("Is Manager"))
    reports_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Reports To"),
    )
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Role"))
    device_location = models.ForeignKey('OfficeLocation',blank=True,null=True,on_delete=models.SET_NULL,verbose_name=_('Device Location'),help_text=_('Where this device is located. For ex: - MCC or Cluster office location'))
    
    def __str__(self):
        if not self.first_name:
            return self.username
        return f"{self.first_name} {self.last_name}"

    def toggle_manager_status(self):
        """
        Toggle the manager status of the employee.
        """
        self.is_rm = not self.is_rm
        self.save()

    class Meta:
        db_table = "tbl_user"
        managed = True
        verbose_name = _("User")
        verbose_name_plural = _("Users")


class Logo(models.Model):
    logo = models.CharField(max_length=100, verbose_name=_("Logo"))
    logo_image = models.ImageField(
        upload_to="logos/", blank=True, null=True, verbose_name=_("Logo Image")
    )

    def __str__(self):
        return f"{self.logo} - {self.logo_image}"

    class Meta:
        db_table = "tbl_logo"
        managed = True
        verbose_name = "Logo"
        verbose_name_plural = "Logos"


class Department(models.Model):
    department = models.CharField(max_length=100, verbose_name=_("Department"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    slug = models.SlugField(unique=True, max_length=100, verbose_name=_("Slug"))
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="department_updated_by",
        null=True,
        verbose_name=_("Created By"),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="department_created_by",
        null=True,
        verbose_name=_("Updated By"),
    )
    description = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.dept)
        super(Department, self).save(*args, **kwargs)

    class Meta:
        db_table = "tbl_department"
        managed = True
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def __str__(self):
        return self.department


class Designation(models.Model):
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, verbose_name=_("Department")
    )
    slug = models.SlugField(unique=True, max_length=100, verbose_name=_("Slug"))
    designation = models.CharField(max_length=100, verbose_name=_("Designation"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="designation_created_by",
        verbose_name=_("Created By"),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="designation_updated_by",
        verbose_name=_("Updated By"),
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.designation}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.designation)
        super(Designation, self).save(*args, **kwargs)

    class Meta:
        db_table = "tbl_designation"
        managed = True
        verbose_name = _("Designation")
        verbose_name_plural = _("Designations")


class Gender(models.Model):
    gender = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="gender_created_by",
        verbose_name=_("Created By"),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="gender_updated_by",
        verbose_name=_("Updated By"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

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


class MaritalStatus(models.Model):
    marital_status = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created AT"))

    def __str__(self):
        return f"{self.marital_status}"

    class Meta:
        db_table = "tbl_marital_status"
        managed = True
        verbose_name = _("Marital Status")
        verbose_name_plural = _("Marital Statuses")


class ParmanentAddress(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="permanent_addresses",
        verbose_name=_("Employee"),
        blank=True,
        null=True,
    )
    address_line_1 = models.CharField(max_length=100, verbose_name=_("Address Line 1"))
    address_line_2 = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Address Line 2")
    )
    country = models.CharField(max_length=50, verbose_name=_("Country"))
    district = models.CharField(max_length=50, verbose_name=_("District"))
    state = models.CharField(max_length=50, verbose_name=_("State"))
    zipcode = models.CharField(max_length=10, verbose_name=_("ZIP Code"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created AT"))

    def __str__(self):
        return f"{self.user.get_full_name()} {self.address_line_1}, {self.state}, {self.zipcode}"

    class Meta:
        db_table = "tbl_permanent_address"
        managed = True
        verbose_name = _("Permanent Address")
        verbose_name_plural = _("Permanent Addresses")


class CorrespondingAddress(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="corres_addresses",
        verbose_name=_("Employee"),
        blank=True,
        null=True,
    )
    address_line_1 = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Address Line 1")
    )
    address_line_2 = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Address Line 2")
    )
    country = models.CharField(
        max_length=50, blank=True, null=True, verbose_name=_("Country")
    )
    district = models.CharField(
        max_length=50, blank=True, null=True, verbose_name=_("District")
    )
    state = models.CharField(
        max_length=50, blank=True, null=True, verbose_name=_("State")
    )
    zipcode = models.CharField(
        max_length=10, blank=True, null=True, verbose_name=_("ZIP Code")
    )

    def __str__(self):
        return f"{self.user.get_full_name()} {self.address_line_1}, {self.state}, {self.zipcode}"

    class Meta:
        db_table = "tbl_correspondence_address"
        managed = True
        verbose_name = _("Corresponding Address")
        verbose_name_plural = _("Corresponding Addresses")


class Religion(models.Model):
    religion = models.CharField(max_length=100, unique=True, verbose_name=_("Religion"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created AT"))

    def __str__(self):
        return self.religion

    class Meta:
        db_table = "tbl_religion"
        managed = True
        verbose_name = _("Religion")
        verbose_name_plural = _("Religions")


class Family(models.Model):
    SPOUSE = "Spouse"
    CHILD = "Child"
    PARENT = "Parent"

    EMPLOYEE_RELATIONSHIP_CHOICES = [
        ("Spouse", "Spouse"),
        ("Child", "Child"),
        ("Parent", "Parent"),
        ("Sibling", "Sibling"),
        ("Other", "Other"),
    ]
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="families"
    )
    member_name = models.CharField(max_length=100, verbose_name=_("Member Name"))
    relationship = models.CharField(
        max_length=20,
        choices=EMPLOYEE_RELATIONSHIP_CHOICES,
        verbose_name=_("Relationship"),
    )
    contact_number = models.CharField(
        max_length=15, blank=True, null=True, verbose_name=_("Contact Number")
    )

    def __str__(self):
        return f"{self.member_name} ({self.relationship}) - {self.user}"

    class Meta:
        db_table = "tbl_family_details"
        managed = True
        verbose_name = _("Family Detail")
        verbose_name_plural = _("Family Details")


class Deduction(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="deductions"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Amount")
    )
    reason = models.CharField(max_length=100, verbose_name=_("Reason"))
    date = models.DateField(verbose_name=_("Date"))

    def __str__(self):
        return f"Deduction of {self.amount} for {self.reason} on {self.date}"

    class Meta:
        db_table = "tbl_deduction"
        managed = True
        verbose_name = _("Deduction")
        verbose_name_plural = _("Deductions")


class PersonalDetails(models.Model):
    employee_code = models.CharField(
        max_length=100,
        unique=True,
        help_text=_(
            "Enter the employee code with company short code prefix, For example: 65"
        ),
        verbose_name=_("Employee Code"),
    )
    user = models.OneToOneField(
        CustomUser, default=0, on_delete=models.CASCADE, related_name="personal_detail"
    )
    avatar = models.FileField(
        upload_to="avatar/", blank=True, null=True, verbose_name=_("Avatar")
    )
    mobile_number = models.CharField(
        max_length=15,
        unique=True,
        help_text=_("Employee person mobile number"),
        verbose_name=_("Mobile Number"),
    )
    alt_mobile_number = models.CharField(
        max_length=15,
        blank=True,
        help_text=_("Employee person alternate mobile number"),
        verbose_name=_("Alternative Mobile Number"),
    )
    cug_mobile_number = models.CharField(
        max_length=15,
        blank=True,
        help_text=_("Employee company provided mobile number if any"),
        verbose_name=_("Company Mobile Number"),
    )
    gender = models.ForeignKey(
        Gender,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Gender"),
    )
    designation = models.ForeignKey(
        Designation, on_delete=models.CASCADE, verbose_name=_("Designation")
    )
    official_mobile_number = models.CharField(
        max_length=15, unique=True, verbose_name=_("Official Mobile Number")
    )
    religion = models.ForeignKey(
        Religion,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Religion"),
    )
    marital_status = models.ForeignKey(
        MaritalStatus,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Marital Status"),
    )
    birthday = models.DateField(null=True, blank=True, verbose_name=_("Birthday"))
    marriage_ann = models.DateField(
        null=True, blank=True, verbose_name=_("Marriage Anniversary")
    )
    ctc = models.DecimalField(
        null=True, blank=True, max_digits=10, decimal_places=2, verbose_name=_("CTC")
    )
    ann_date = models.DateField(
        null=True, blank=True, verbose_name=_("Job Anniversary")
    )
    doj = models.DateField(verbose_name=_("Date of Joining"))
    dol = models.DateField(null=True, blank=True, verbose_name=_("Date of Leaving"))
    dor = models.DateField(null=True, blank=True, verbose_name=_("Date of Resignation"))
    dof = models.DateField(
        null=True, blank=True, verbose_name=_("Date of Final Settlement")
    )
    updated_at = models.DateTimeField(
        null=True, blank=True, auto_now_add=True, verbose_name=_("Updated At")
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pd_created_by",
        verbose_name=_("Created By"),
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pd_updated_by",
        verbose_name=_("Updated By"),
    )
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))

    def __str__(self):
        return f"Personal Details of {self.user.first_name} - {self.mobile_number}"

    class Meta:
        db_table = "tbl_personal_details"
        managed = True
        verbose_name = _("Personal Detail")
        verbose_name_plural = _("Personal Details")


from django.utils import timezone
from datetime import timedelta

class ShiftTiming(models.Model):
    start_time = models.TimeField(verbose_name=_("Start Time"))
    end_time = models.TimeField(verbose_name=_("End Time"))
    grace_time = models.IntegerField(blank=True, null=True, verbose_name=_("Grace Time"))
    grace_start_time = models.TimeField(blank=True, null=True, verbose_name=_("Grace Start Time"))
    grace_end_time = models.TimeField(blank=True, null=True, verbose_name=_("Grace End Time"))

    # Break time range fields
    break_start_time = models.TimeField(blank=True, null=True, verbose_name=_("Break Start Time"))
    break_end_time = models.TimeField(blank=True, null=True, verbose_name=_("Break End Time"))

    # Field to store break duration
    break_duration = models.IntegerField(
        blank=True, null=True, verbose_name=_("Break Duration (minutes)")
    )

    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Role"))
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    def save(self, *args, **kwargs):
        """
        Override the save method to automatically calculate break duration
        when break_start_time and break_end_time are provided.
        """
        if self.break_start_time and self.break_end_time:
            # Convert times to datetime objects for subtraction
            break_start = timezone.datetime.combine(timezone.now().date(), self.break_start_time)
            break_end = timezone.datetime.combine(timezone.now().date(), self.break_end_time)

            # Calculate the difference and store the duration in minutes
            duration = break_end - break_start
            self.break_duration = duration.total_seconds() // 60  # Convert seconds to minutes
        else:
            self.break_duration = None  # Reset if break times are not provided

        super().save(*args, **kwargs)

    class Meta:
        db_table = "tbl_shift_timing"
        verbose_name = _("Shift Timing")
        verbose_name_plural = _("Shift Timings")



class EmployeeShift(models.Model):
    employee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name=_("Employee"),
    )
    shift_timing = models.ForeignKey(
        ShiftTiming, on_delete=models.CASCADE, verbose_name=_("Shift Timing")
    )
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created By"),
        related_name="shift_created",
    )

    class Meta:
        db_table = "tbl_employee_shift"

    def __str__(self):
        return f"{self.employee.username}:  {self.shift_timing}"


class SalaryDetails(models.Model):
    employee = models.OneToOneField(PersonalDetails, on_delete=models.CASCADE)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    ta = models.DecimalField(max_digits=10, decimal_places=2)
    da = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    hra = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    conveyance_allowance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lta = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    esi_employer_contribution = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    esi_employee_contribution = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    pf_employer_contribution = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    pf_employee_contribution = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    professional_tax = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    labor_welfare_fund = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    special_allowance = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    net_salary = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )

    def generate_salary(self):
        # Basic
        basic_percentage_range = getattr(settings, "BASIC_PERCENTAGE_RANGE", (0.4, 0.5))
        basic_percentage = random.uniform(*basic_percentage_range)
        self.basic_salary = self.employee.ctc * basic_percentage

        # DA
        da_percentage = getattr(settings, "DA_PERCENTAGE", 0.05)
        self.da = self.employee.ctc * da_percentage

        # HRA
        hra_percentage_metro = getattr(settings, "HRA_PERCENTAGE_METRO", 0.5)
        hra_percentage_non_metro = getattr(settings, "HRA_PERCENTAGE_NON_METRO", 0.4)
        if self.employee.location == "metro":
            self.hra = (self.basic_salary + self.da) * hra_percentage_metro
        else:
            self.hra = (self.basic_salary + self.da) * hra_percentage_non_metro

        # LTA
        lta_percentage = getattr(settings, "LTA_PERCENTAGE", 0.10)
        self.lta = self.basic_salary * lta_percentage

        esi_employer_percentage = getattr(settings, "ESI_EMPLOYER_PERCENTAGE", 0.0475)
        esi_employee_percentage = getattr(settings, "ESI_EMPLOYEE_PERCENTAGE", 0.0175)
        self.esi_employer_contribution = (
            self.basic_salary + self.da + self.hra
        ) * esi_employer_percentage
        self.esi_employee_contribution = (
            self.basic_salary + self.da + self.hra
        ) * esi_employee_percentage

        # PF
        pf_employer_percentage = getattr(settings, "PF_EMPLOYER_PERCENTAGE", 0.12)
        pf_employee_percentage = getattr(settings, "PF_EMPLOYEE_PERCENTAGE", 0.12)
        self.pf_employer_contribution = (
            self.basic_salary + self.da
        ) * pf_employer_percentage
        self.pf_employee_contribution = (
            self.basic_salary + self.da
        ) * pf_employee_percentage

        # Professional Tax
        professional_tax = getattr(settings, "PROFESSIONAL_TAX", 0)
        self.professional_tax = professional_tax

        # Labor Welfare Fund
        labor_welfare_fund = getattr(settings, "LABOR_WELFARE_FUND", 0)
        self.labor_welfare_fund = labor_welfare_fund

        # Special Allowance (Balancing component)
        total_earnings = (
            self.basic_salary
            + self.da
            + self.hra
            + self.conveyance_allowance
            + self.medical_allowance
            + self.lta
            + self.special_allowance
        )
        total_deductions = (
            self.esi_employer_contribution
            + self.pf_employer_contribution
            + self.professional_tax
            + self.labor_welfare_fund
        )
        self.special_allowance = total_earnings - total_deductions

        self.net_salary = total_earnings - total_deductions

    def __str__(self):
        return f"Salary Details {self.basic_salary}"

    class Meta:
        db_table = "tbl_sal_detail"
        managed = True
        verbose_name = "Salary Detail"
        verbose_name_plural = "Salary Details"


class BankDetails(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    branch_name = models.CharField(max_length=100)
    IFSC_code = models.CharField(max_length=20)
    pan_number = models.CharField(max_length=10)

    def __str__(self):
        return f"Bank Details of {self.user.first_name} - {self.bank_name} , {self.IFSC_code}, {self.branch_name}"

    class Meta:
        db_table = "tbl_bank_detail"
        managed = True
        verbose_name = "Bank Detail"
        verbose_name_plural = "Bank Details"


from django.utils import timezone


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
        max_length=200, unique=True, verbose_name=_("Application No")
    )
    appliedBy = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="leaves",
        verbose_name=_("Applied By"),
    )
    applyingDate = models.DateTimeField(auto_now=True, verbose_name=_("Applying Date"))
    startDate = models.DateTimeField(verbose_name=_("Start Date"))
    endDate = models.DateTimeField(blank=True, null=True, verbose_name=_("End Date"))
    usedLeave = models.FloatField(verbose_name=_("Used Leave"))
    balanceLeave = models.FloatField(verbose_name=_("Balance Leave"))
    reason = models.TextField(blank=True, verbose_name=_("Reason"))
    status = models.CharField(
        max_length=30,
        choices=settings.LEAVE_STATUS_CHOICES,
        default=settings.PENDING,
        verbose_name=_("Status"),
    )
    startDayChoice = models.CharField(
        max_length=20,
        default=settings.FULL_DAY,
        choices=settings.START_LEAVE_TYPE_CHOICES,
        verbose_name=_("Start Day Choice"),
    )
    endDayChoice = models.CharField(
        max_length=20,
        default=settings.FULL_DAY,
        choices=settings.START_LEAVE_TYPE_CHOICES,
        verbose_name=_("End Day Choice"),
    )
    updatedAt = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))
    slug = models.SlugField(
        max_length=255, unique=True, blank=True, editable=False, verbose_name=_("Slug")
    )

    def save(self, *args, **kwargs):
        # Generate unique application number
        if not self.applicationNo:
            self.applicationNo = self.generate_unique_application_no()

        # Generate the slug
        if not self.slug:
            base_slug = f"{self.appliedBy.get_full_name()}-{self.startDate.strftime('%Y-%m-%d')}-{self.startDayChoice}"
            unique_slug = slugify(base_slug)
            num = 1
            while LeaveApplication.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{slugify(base_slug)}-{num}"
                num += 1
            self.slug = unique_slug

        super().save(*args, **kwargs)

    def generate_unique_application_no(self):
        """Generate a unique application number."""
        while True:
            # Generate a random application number
            random_str = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=4)
            )
            application_no = f"Leave/{self.leave_type.leave_type}/{random_str}"
            if not LeaveApplication.objects.filter(
                applicationNo=application_no
            ).exists():
                return application_no

    def __str__(self):
        return f"Leave Application {self.applicationNo} for {self.appliedBy}"

    def approve_leave(self, action_by):
        if self.status == settings.PENDING:
            self.status = settings.APPROVED
            self.save(update_fields=["status", "updatedAt"])
            LeaveLog.create_log(self, action_by, settings.APPROVED)

    def reject_leave(self, action_by):
        if self.status == settings.PENDING:
            self.status = settings.REJECTED
            self.save(update_fields=["status", "updatedAt"])
            LeaveLog.create_log(self, action_by, settings.REJECTED)

    def cancel_leave(self, action_by):
        if self.status == settings.APPROVED:
            self.status = settings.CANCELLED
            self.save(update_fields=["status", "updatedAt"])
            LeaveLog.create_log(self, action_by, settings.CANCELLED)

    @classmethod
    def create_leave_application(
        cls,
        applied_by,
        application_no,
        start_date,
        end_date,
        used_leave,
        balance_leave,
        reason,
        start_day_choice,
        end_day_choice,
    ):
        leave_application = cls.objects.create(
            appliedBy=applied_by,
            applicationNo=application_no,
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

import uuid

class OfficeLocation(models.Model):
    # Using UUID as the primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Unique Identifier",
        help_text="Unique ID for this location, generated automatically."
    )

    # Name and type of the location
    location_name = models.CharField(
        max_length=100,
        verbose_name="Location Name",
        help_text="Enter the name of the location (e.g., Head Office, Cluster Office, etc.)"
    )
    office_type = models.CharField(
        max_length=50,
        choices=settings.OFFICE_TYPE_CHOICES,
        verbose_name="Office Type",
        help_text="Specify the type of office (Head Office, Cluster Office, MCC, BMC, MPP)."
    )

    # Address and coordinates
    address = models.TextField(
        verbose_name="Address",
        help_text="Enter the complete address of the location."
    )
    
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        verbose_name="Latitude",
        help_text="Enter the latitude of the location.",
        blank=True,
        null=True
    )
    
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        verbose_name="Longitude",
        help_text="Enter the longitude of the location.",
        blank=True,
        null=True
    )

    # Metadata fields
    created_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Created At",
        help_text="The date and time when this record was created."
    )
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Updated At",
        help_text="The date and time when this record was last updated."
    )
    created_by = models.ForeignKey(
        CustomUser, related_name='location_created_by',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Created By",
        help_text="The user who created this record."
    )
    updated_by = models.ForeignKey(
        CustomUser, related_name='location_updated_by',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Updated By",
        help_text="The user who last updated this record."
    )

    class Meta:
        verbose_name = "Office Location"
        verbose_name_plural = "Office Locations"
        ordering = ['location_name']

    def __str__(self):
        return f"{self.location_name} ({self.office_type})"

    def save(self, *args, **kwargs):
        """
        Override the save method to include custom logic for automatically populating
        `created_by` and `updated_by` fields based on the authenticated user.
        """
        # Expecting 'user' to be passed in kwargs when calling save()
        user = kwargs.pop('user', None)
        if user:
            if not self.pk:  # If the object is being created
                self.created_by = user
            self.updated_by = user  # Always set updated_by

        super(OfficeLocation, self).save(*args, **kwargs)
        
class DeviceInformation(models.Model):
    device_location = models.ForeignKey(OfficeLocation,blank=True,null=True,on_delete=models.SET_NULL,verbose_name=_('Device Location'),help_text=_('Where this device is located. For ex: - MCC or Cluster office location'))
    from_date = models.DateTimeField(
        verbose_name=_("From Date"),
        help_text=_("Enter the start date and time for the transaction log.")
    )
    to_date = models.DateTimeField(
        verbose_name=_("To Date"),
        help_text=_("Enter the end date and time for the transaction log.")
    )
    serial_number = models.CharField(
        max_length=50,
        verbose_name=_("Serial Number"),
        help_text=_("Enter the device serial number."),
        unique=True  # Ensure serial numbers are unique
    )
    username = models.CharField(
        max_length=30,
        verbose_name=_("Username"),
        help_text=_("Enter the API username for authentication.")
    )
    password = models.CharField(
        max_length=50,
        verbose_name=_("Password"),
        help_text=_("Enter the API password for authentication.")
    )
    api_link = models.URLField(
        max_length=200,  # Increase if necessary to accommodate long URLs
        verbose_name=_("API Link"),
        help_text=_("Enter the API link for the device."),
        default="http://1.22.197.176:99/iclock/WebAPIService.asmx"  # Default link can be modified if needed
    )
    
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
        max_length=20, choices=settings.START_LEAVE_TYPE_CHOICES, verbose_name="Start Day Choice"
    )
    end_day_choice = models.CharField(
        max_length=20, choices=settings.START_LEAVE_TYPE_CHOICES, verbose_name="End Day Choice"
    )
    adjustment_value = models.FloatField(verbose_name="Adjustment Value")

    def __str__(self):
        return f"{self.start_day_choice} to {self.end_day_choice} adjustment: {self.adjustment_value}"

    class Meta:
        unique_together = ('start_day_choice', 'end_day_choice')
        verbose_name = "Leave Day Choice Adjustment"
        verbose_name_plural = "Leave Day Choice Adjustments"

class LeaveType(models.Model):
    leave_type = models.CharField(
        max_length=100,
        unique=True,
        choices=settings.LEAVE_TYPE_CHOICES,
        verbose_name=_("Leave Type"),
        help_text=_("Select the type of leave (e.g., Sick Leave, Casual Leave). This must be unique.")
    )
    leave_type_short_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Leave Type Short Code"),
        help_text=_("Provide a short code for the leave type (optional). This must be unique if provided.")
    )
    default_allocation = models.FloatField(
        blank=True, null=True, 
        verbose_name=_("Default Allocation"),
        help_text=_("Set the default number of days allocated for this leave type.")
    )
    min_notice_days = models.FloatField(
        blank=True, null=True,
        verbose_name=_("Minimum Notice Days"),
        help_text=_("Specify the minimum number of days notice required before applying for this leave.")
    )
    max_days_limit = models.FloatField(
        blank=True, null=True,
        verbose_name=_("Maximum Days Limit"),
        help_text=_("Set the maximum number of consecutive days that can be taken for this leave type.")
    )
    min_days_limit = models.FloatField(
        blank=True, null=True,
        verbose_name=_("Minimum Days Limit"),
        help_text=_("Set the minimum number of consecutive days that can be taken for this leave type.")
    )
    allowed_days_per_year = models.FloatField(
        blank=True, null=True,
        verbose_name=_("Allowed Days Per Year"),
        help_text=_("Specify the total number of days allowed for this leave type per year.")
    )
    leave_fy_start = models.DateField(
        blank=True, null=True,
        verbose_name="Leave FY Start",
        help_text=_("Define the start of the financial year for leave calculations (optional).")
    )
    leave_fy_end = models.DateField(
        blank=True, null=True,
        verbose_name="Leave FY End",
        help_text=_("Define the end of the financial year for leave calculations (optional).")
    )
    color_hex = models.CharField(
        max_length=7, blank=True, null=True,
        verbose_name=_("Color Hex Code"),
        help_text=_("Enter a hex color code to represent this leave type in the system.")
    )
    text_color_hex = models.CharField(
        max_length=7, blank=True, null=True,
        verbose_name=_("Text Color Hex Code"),
        help_text=_("Enter a hex color code for the text color to be used with this leave type.")
    )
    created_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when this leave type was created (automatically set).")
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="created_leave_types",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
        help_text=_("The user who created this leave type (set automatically).")
    )
    updated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when this leave type was last updated (automatically set).")
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="updated_leave_types",
        null=True,
        blank=True,
        verbose_name=_("Updated By"),
        help_text=_("The user who last updated this leave type (set automatically).")
    )

    consecutive_restriction = models.BooleanField(
        default=False,
        verbose_name=_("Consecutive Leave Restriction"),
        help_text=_("Check if consecutive leave applications are not allowed for this leave type.")
    )
    restricted_after_leave_types = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="restricted_by_leave_types",
        verbose_name=_("Restricted After Leave Types"),
        help_text=_("Select leave types after which this leave type cannot be applied consecutively.")
    )


    def __str__(self):
        return f"{self.leave_type}"

    class Meta:
        db_table = "tbl_leave_type"
        managed = True
        verbose_name = _("Leave Type")
        verbose_name_plural = _("Leave Types")


class LeaveBalanceOpenings(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        verbose_name=_("User"),
        help_text=_("The user for whom this leave balance is being recorded.")
    )
    no_of_leaves = models.FloatField(
        blank=True, 
        null=True, 
        verbose_name=_("Number of Leaves"),
        help_text=_("The total number of leaves allocated to the user for this leave type.")
    )
    remaining_leave_balances = models.FloatField(
        blank=True, 
        null=True, 
        verbose_name=_("Remaining Leave Balance"),
        help_text=_("The remaining balance of leaves available to the user for this leave type.")
    )
    leave_type = models.ForeignKey(
        LeaveType, 
        on_delete=models.CASCADE, 
        null=True, 
        verbose_name=_("Leave Type"),
        help_text=_("The type of leave for which the balance is being recorded.")
    )
    year = models.PositiveIntegerField(
        default=timezone.now().year, 
        verbose_name=_("Year"),
        help_text=_("The year for which the leave balance applies.")
    )
    created_at = models.DateTimeField(
        auto_now=True, 
        verbose_name=_("Created At"),
        help_text=_("The date and time when this leave balance record was created.")
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="created_leave_balances",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
        help_text=_("The user who created this leave balance record.")
    )
    updated_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_("Updated At"),
        help_text=_("The date and time when this leave balance record was last updated.")
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="updated_leave_balances",
        null=True,
        blank=True,
        verbose_name=_("Updated By"),
        help_text=_("The user who last updated this leave balance record.")
    )

    class Meta:
        db_table = "tbl_leave_bal"
        managed = True
        verbose_name = _("Leave Balance")
        verbose_name_plural = _("Leave Balances")
        unique_together = ("leave_type", "user", "year")

    def __str__(self):
        return f"Leave Balance for {self.user.first_name} {self.user.last_name} - {self.leave_type} ({self.remaining_leave_balances})"

    @classmethod
    def initialize_leave_balances(cls, user, leave_types, year, created_by):
        """
        Initialize leave balances for a user with multiple leave types in bulk.
        """
        leave_balances = []

        # Iterate through leave types to create LeaveBalanceOpening instances
        for leave_type in leave_types:
            leave_balance = cls(
                user=user,
                leave_type=leave_type,
                year=year,
                no_of_leaves=leave_type.default_allocation,
                remaining_leave_balances=leave_type.default_allocation,
                created_by=created_by,
                updated_by=created_by,
            )
            leave_balances.append(leave_balance)
        
        # Bulk create to insert multiple records in a single query
        with transaction.atomic():  # Ensure atomic transaction
            cls.objects.bulk_create(leave_balances)


class CompensatoryOff(models.Model):
    # Primary key as UUID
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Unique ID"
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='compensatory_offs',
        verbose_name="User",
        help_text="The employee who earned this compensatory off."
    )
    worked_on = models.DateField(
        verbose_name="Worked On",
        help_text="The date on which the employee worked to earn the compensatory off."
    )
    expiry_date = models.DateField(
        verbose_name="Expiry Date",
        help_text="The date on which the compensatory off expires."
    )
    reason = models.TextField(
        null=True, blank=True,
        verbose_name="Reason",
        help_text="Reason for working on the day and earning compensatory off."
    )

    status = models.CharField(
        max_length=20,
        choices=settings.CO_STATUS_CHOICES,
        default=settings.OPEN,
        verbose_name="Status",
        help_text="The current status of the compensatory off."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Automatically set the expiry date if it's not provided
        if not self.expiry_date:
            self.expiry_date = self.worked_on + timedelta(days=30)
        
        # Update status to 'expired' if expiry date has passed and status is still 'open'
        if self.status == 'open' and self.expiry_date < timezone.now().date():
            self.status = 'expired'
            
        super(CompensatoryOff, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - CO on {self.worked_on} (Status: {self.status})"


class Notification(models.Model):

    sender = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        verbose_name="Sender",
        related_name='notifications_sent',
        help_text="The user who sent the notification."
    )
    
    receiver = models.ForeignKey(
        'CustomUser',
        related_name='notifications',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Receiver",
        help_text="The user who receives the notification."
    )
    
    message = models.CharField(
        max_length=255,
        verbose_name="Notification Message",
        help_text="The content of the notification."
    )
    
    notification_type = models.CharField(
        max_length=50,
        choices=settings.NOTIFICATION_TYPES,
        null=True,
        blank=True,
        verbose_name="Notification Type",
        help_text="The type of notification being sent."
    )
    
    # Fields to store related object information
    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Related Object ID",
        help_text="The ID of the related object associated with this notification."
    )
    
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Related Content Type",
        help_text="The type of the related object (model) this notification is linked to."
    )
    
    related_object = GenericForeignKey('related_content_type', 'related_object_id')

    target_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Target URL",
        help_text="The URL for web navigation related to this notification."
    )
    
    go_route_mobile = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Mobile Deep Link",
        help_text="The mobile deep link for navigating to the related content."
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Timestamp",
        help_text="The time when the notification was created."
    )
    
    is_read = models.BooleanField(
        default=False,
        verbose_name="Read Status",
        help_text="Indicates whether the notification has been read."
    )

    def __str__(self):
        return f"{self.notification_type}: {self.message}"

    class Meta:
        db_table = "tbl_notification"
        managed = True
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"


class NotificationSetting(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    receive_notifications = models.BooleanField(default=True)
    receive_sound_notifications = models.BooleanField(default=True)
    receive_desktop_notifications = models.BooleanField(default=True)
    receive_mobile_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"Notification settings for {self.user.username}"

    class Meta:
        db_table = "tbl_chat_notification_settings"
        managed = True
        verbose_name = "Chat Notification Setting"
        verbose_name_plural = "Chat Notifications Settings"


class Holiday(models.Model):
    title = models.CharField(max_length=100, verbose_name=_("Title"))
    short_code = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Short Code"))
    start_date = models.DateField(blank=True, null=True, verbose_name=_("Start Date"))
    end_date = models.DateField(blank=True, null=True, verbose_name=_("End Date"))
    desc = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    color_hex = models.CharField(
        max_length=7, blank=True, null=True, verbose_name=_("Color Hex Code")
    )
    created_at = models.DateTimeField(auto_now=True, verbose_name=_("Created At"))
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="created_holidays",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
    )
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Updated At"))
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="updated_holidays",
        null=True,
        blank=True,
        verbose_name=_("Updated By"),
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_by = kwargs.pop("created_by", None)
        self.updated_by = kwargs.pop("updated_by", None)
        super(Holiday, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.start_date}"

    class Meta:
        db_table = "tbl_holidays"
        managed = True
        verbose_name = _("Holiday")
        verbose_name_plural = _("Holidays")



class UserTour(models.Model):
    applied_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="tours",
        verbose_name=_("Applied By"),
    )
    from_destination = models.CharField(
        max_length=255, verbose_name=_("From Destination")
    )
    to_destination = models.CharField(max_length=255, verbose_name=_("To Destination"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    start_time = models.TimeField(verbose_name=_("Start Time"), blank=True, null=True)
    end_date = models.DateField(verbose_name=_("End Date"))
    end_time = models.TimeField(verbose_name=_("End Time"), blank=True, null=True)
    updatedAt = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Updated At"), blank=True, null=True
    )
    createdAt = models.DateTimeField(
        auto_now=True, verbose_name=_("Created At"), blank=True, null=True
    )
    remarks = models.TextField(null=True, blank=True, verbose_name=_("Remarks"))
    status = models.CharField(
        max_length=50,
        choices=settings.TOUR_STATUS_CHOICES,
        default=settings.PENDING,
        verbose_name=_("Status"),
    )
    extended_end_date = models.DateField(
        null=True, blank=True, verbose_name=_("Extended End Date")
    )
    extended_end_time = models.TimeField(
        null=True, blank=True, verbose_name=_("Extended End Date")
    )
    bills_submitted = models.BooleanField(
        default=False, verbose_name=_("Bills Submitted")
    )
    slug = models.SlugField(
        max_length=255, blank=True, null=True, verbose_name=_("Slug")
    )
    approval_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=settings.APPROVAL_TYPE_CHOICES,
        verbose_name=_("Approval Type"),
    )

    def __str__(self):
        return f"Tour {self.id} by {self.applied_by.username}"

    def approve(self, action_by, reason=None):
        self.status = settings.APPROVED
        self.save(update_fields=["status", "updatedAt"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Approved by {action_by.username}. Reason: {reason}",
        )

    def reject(self, action_by, reason=None):
        self.status = settings.REJECTED
        self.save(update_fields=["status", "updatedAt"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Rejected by {action_by.username}. Reason: {reason}",
        )

    def cancel(self, action_by, reason=None):
        self.status = settings.CANCELLED
        self.save(update_fields=["status", "updatedAt"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Cancelled by {action_by.username}. Reason: {reason}",
        )
        
    def pending_cancel(self, action_by, reason=None):
        self.status = settings.PENDING_CANCELLATION
        self.save(update_fields=["status", "updatedAt"])
    
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Pending Cancellation by {action_by.username}. Reason: {reason}",
        )

    def complete(self, action_by, reason=None):
        comments = reason or "Tour completed"
        self.status = settings.COMPLETED
        self.save(update_fields=["status", "updatedAt"])
        TourStatusLog.create_log(
            tour=self, action_by=action_by, action=self.status, comments=comments
        )

    def extend(self, action_by, new_end_date, new_end_time, reason=None):
        self.extended_end_date = new_end_date
        self.extended_end_time = new_end_time
        self.status = settings.EXTENDED
        self.save(update_fields=["status","extended_end_date","extended_end_time" ,"updatedAt"])
        TourStatusLog.create_log(
            tour=self,
            action_by=action_by,
            action=self.status,
            comments=f"Tour extended to {new_end_date} {new_end_time}. Reason {reason} ",
        )

    class Meta:
        db_table = "tbl_user_tours"
        managed = True
        verbose_name = _("User Tour")
        verbose_name_plural = _("Users' Tours")


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


class AttendanceLog(models.Model):
    applied_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="attendance_log",
        verbose_name=_("Applied By"),
    )
    start_date = models.DateTimeField(verbose_name=_("Start Date"))
    end_date = models.DateTimeField(verbose_name=_("End Date"))
    from_date = models.DateTimeField(blank=True, null=True, verbose_name=_("From Date"))
    to_date = models.DateTimeField(blank=True, null=True, verbose_name=_("To Date"))
    reg_duration = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Regularization Duration")
    )
    slug = models.SlugField(
        max_length=255, unique=True, blank=True, verbose_name=_("Slug")
    )
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    is_regularisation = models.BooleanField(
        default=False, verbose_name=_("Is Regularisation")
    )
    duration = models.TimeField(blank=True, null=True, verbose_name=_("Duration"))
    reg_status = models.CharField(
        max_length=20,
        choices=settings.ATTENDANCE_REGULARISED_STATUS_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Regularization Status"),
    )
    status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=settings.ATTENDANCE_LOG_STATUS_CHOICES,
        verbose_name=_("Status"),
    )
    att_status = models.CharField(
        max_length=20,
        choices=settings.ATTENDANCE_STATUS_CHOICES,
        verbose_name=_("Attendance Status"),
    )
    att_status_short_code = models.CharField(
        max_length=20,verbose_name=_("Short Code"),
        blank=True, null=True,
    )
    color_hex = models.CharField(
        max_length=7, blank=True, null=True, verbose_name=_("Color Hex Code")
    )
    created_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name=_("Updated By"),
        blank=True,
        null=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    reason = models.CharField(
        max_length=100, verbose_name=_("Reason"), blank=True, null=True
    )
    is_submitted = models.BooleanField(
        default=False,
        verbose_name=_("Is Submitted"),
        help_text=_(
            "This is a boolean flag to handle if regularization is submitted or not."
        ),
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super(AttendanceLog, self).save(*args, **kwargs)

    def __str__(self):
        return self.title
    
    def approve(self, action_by, reason=None):
        self.status = settings.APPROVED
        self.save(update_fields=["status", "updatedAt"])
        self.add_action(action=self.status,performed_by=action_by,comment=reason)

    def reject(self, action_by, reason=None):
        self.status = settings.REJECTED
        self.save(update_fields=["status", "updatedAt"])
        self.add_action(action=self.status,performed_by=action_by,comment=reason)
        
    def recommend(self, action_by, reason=None):
        self.status = settings.RECOMMEND
        self.save(update_fields=["status", "updatedAt"])
        self.add_action(action=self.status,performed_by=action_by,comment=reason)
        

    def notrecommend(self, action_by, reason=None):
        self.status = settings.NOT_RECOMMEND
        self.save(update_fields=["status", "updatedAt"])
        self.add_action(action=self.status,performed_by=action_by,comment=reason)
        

    class Meta:
        db_table = "tbl_events"
        managed = True
        verbose_name = _("Attendance Log")
        verbose_name_plural = _("Attendance Logs")

    def add_action(self, action, performed_by, comment=None):
        AttendanceLogAction.create_log(
            self, action=action, action_by=performed_by, notes=comment
        )


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


class EmployeeImage(models.Model):
    image = models.ImageField(upload_to="employee_images/")
    employee_code = models.CharField(max_length=100, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    profile_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee_code} - {self.email}"

    class Meta:
        db_table = "tbl_employee_images"
        managed = True
        verbose_name = _("Employee Image")
        verbose_name_plural = _("Employee Images")


class EmployeeClassMapping(models.Model):
    employee_code = models.CharField(max_length=100, unique=True)
    class_index = models.IntegerField(unique=True)

    def __str__(self):
        return f"{self.employee_code} - {self.class_index}"
