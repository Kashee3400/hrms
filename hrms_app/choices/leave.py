from django.db import models
from django.utils.translation import gettext_lazy as _


class LeaveUnit(models.TextChoices):
    DAY = "DAY", _("Day")
    HOUR = "HOUR", _("Hour")
    MINUTE = "MINUTE", _("Minute")


class LeaveAccrualPeriod(models.TextChoices):
    NONE = "NONE", _("No Accrual")
    MONTHLY = "MONTHLY", _("Monthly")
    YEARLY = "YEARLY", _("Yearly")


class LeaveExpiryPolicy(models.TextChoices):
    NONE = "NONE", _("No Expiry")
    PERIOD_END = "PERIOD_END", _("Expire at Period End")
    FY_END = "FY_END", _("Expire at Financial Year End")

