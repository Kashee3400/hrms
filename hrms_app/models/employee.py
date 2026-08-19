from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.templatetags.static import static


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
        auto_now_add=True,
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
        return f"Bank Details of {self.user.first_name} - {self.bank_name}, {self.ifsc_code}, {self.branch_name}"

    def clean(self):
        if len(self.pan_number) != 10:
            raise ValidationError(_("PAN number must be exactly 10 characters long."))


