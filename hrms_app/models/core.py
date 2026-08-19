from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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


