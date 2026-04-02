"""
models_leave_policy_config.py

NEW MODEL: LeavePolicyConfig
────────────────────────────
- Versioned policy rules per LeaveType
- effective_from / effective_to allows mid-year policy changes
- Grandfathered behavior: approved leaves always checked against the
  policy version active on their original start_date
- LeavePolicyManager fetches the correct version via get_active_policy()
- Falls back to LeaveType legacy fields if no config exists yet
  (backward compatibility — zero data loss)

Add this to your existing models.py (or a new leave_policy_config.py
that you import in models.py).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from .models import LeaveType


# ─────────────────────────────────────────────
# ENUMS / CHOICES
# ─────────────────────────────────────────────

class AccrualPeriod(models.TextChoices):
    NONE        = "none",        _("No Accrual")
    MONTHLY     = "monthly",     _("Monthly")
    QUARTERLY   = "quarterly",   _("Quarterly")
    YEARLY      = "yearly",      _("Yearly")


class CalculationPeriod(models.TextChoices):
    CALENDAR_YEAR  = "calendar_year",  _("Calendar Year (Jan–Dec)")
    FINANCIAL_YEAR = "financial_year", _("Financial Year (Apr–Mar)")


class LeaveEncashmentTrigger(models.TextChoices):
    IN_SERVICE      = "in_service",     _("In Service (periodic)")
    SEPARATION      = "separation",     _("Cessation of Contract")
    RETIREMENT      = "retirement",     _("Retirement / Superannuation")
    RESIGNATION     = "resignation",    _("Resignation")
    CRITICAL_HEALTH = "critical_health",_("Critical Health Condition")
    DISABILITY      = "disability",     _("Temporary / Permanent Disability")
    MARRIAGE        = "marriage",       _("Marriage of Self / Child")


# ─────────────────────────────────────────────
# MAIN MODEL
# ─────────────────────────────────────────────

class LeavePolicyConfig(models.Model):
    """
    Versioned leave policy rules.

    One LeaveType can have many LeavePolicyConfig rows, each covering
    a non-overlapping date range.  The row with effective_to=NULL is
    the currently active policy for that leave type.

    How versioning works
    ────────────────────
    - When you create the first config for a leave type, set
      effective_from = date the policy starts, effective_to = None.
    - When the policy changes, close the old row
      (set effective_to = day before new policy) and create a new row.
    - LeavePolicyManager.get_active_policy(leave_type, reference_date)
      always resolves the correct version for a given date.
    - Approved/grandfathered leaves are re-validated against the policy
      version active on their original startDate, not today's policy.
    """

    # ── Identity ────────────────────────────────────────────────────
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name="policy_versions",
        verbose_name=_("Leave Type"),
    )

    # ── Versioning ──────────────────────────────────────────────────
    effective_from = models.DateField(
        verbose_name=_("Effective From"),
        help_text=_("Date from which this policy version is active."),
    )
    effective_to = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Effective To"),
        help_text=_(
            "Date until which this policy version is active. "
            "Leave blank for the currently active version."
        ),
    )

    # ── Entitlement ─────────────────────────────────────────────────
    annual_entitlement = models.FloatField(
        verbose_name=_("Annual Entitlement (Days)"),
        help_text=_("Total days credited per year. e.g. CL=10, SL=10, EL=30"),
    )
    accrual_period = models.CharField(
        max_length=20,
        choices=AccrualPeriod.choices,
        default=AccrualPeriod.YEARLY,
        verbose_name=_("Accrual Period"),
        help_text=_(
            "How often leave is credited. "
            "EL=quarterly, CL/SL=yearly."
        ),
    )
    calculation_period = models.CharField(
        max_length=20,
        choices=CalculationPeriod.choices,
        default=CalculationPeriod.CALENDAR_YEAR,
        verbose_name=_("Calculation Period"),
        help_text=_("CL/SL use Calendar Year; EL uses Financial Year."),
    )

    # ── Application Rules ───────────────────────────────────────────
    min_notice_days = models.FloatField(
        default=1,
        verbose_name=_("Minimum Notice Days"),
        help_text=_(
            "How many days in advance must the leave be applied. "
            "CL/SL=1, EL=7."
        ),
    )
    max_consecutive_days = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Max Consecutive Days"),
        help_text=_("Max days in a single application. CL=5, EL=no limit."),
    )
    min_days_per_application = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Min Days Per Application"),
        help_text=_("Minimum days per single application. EL=3."),
    )
    max_spells_per_year = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Spells Per Year"),
        help_text=_("Max number of separate applications per year. EL=5."),
    )
    allow_half_day = models.BooleanField(
        default=False,
        verbose_name=_("Allow Half Day"),
        help_text=_("CL=True (half-day allowed), EL=restricted (prefix/suffix only)."),
    )
    half_day_only_as_prefix_suffix = models.BooleanField(
        default=False,
        verbose_name=_("Half Day Only as Prefix / Suffix"),
        help_text=_(
            "EL-specific: half-day EL is only permitted as a prefix or "
            "suffix to more than one day of EL."
        ),
    )
    retrospective_application_working_days = models.IntegerField(
        default=3,
        verbose_name=_("Retrospective Application Window (Working Days)"),
        help_text=_(
            "For urgent/unforeseen leave: application must be submitted within "
            "this many working days after the absence. CL/SL=3."
        ),
    )

    # ── Probation / Confirmation ─────────────────────────────────────
    requires_confirmation = models.BooleanField(
        default=False,
        verbose_name=_("Requires Confirmation (Post-Probation)"),
        help_text=_("EL=True: only confirmed employees can avail."),
    )

    # ── Combination Rules ────────────────────────────────────────────
    cannot_combine_with_any = models.BooleanField(
        default=False,
        verbose_name=_("Cannot Combine With Any Other Leave"),
        help_text=_("CL=True: CL cannot be clubbed with any other leave type."),
    )
    can_club_with = models.ManyToManyField(
        LeaveType,
        blank=True,
        symmetrical=False,
        related_name="clubbable_policies",
        verbose_name=_("Can Club With"),
        help_text=_(
            "Specific leave types this leave CAN be combined with. "
            "SL can club with EL in medical emergency."
        ),
    )

    # ── Carry Forward & Accumulation ────────────────────────────────
    allow_carry_forward = models.BooleanField(
        default=False,
        verbose_name=_("Allow Carry Forward"),
    )
    max_carry_forward_days = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Max Carry Forward Days"),
        help_text=_("EL=300. Excess lapses automatically at year end."),
    )
    max_accumulation_days = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Max Accumulation Days"),
        help_text=_("SL=180, EL=300. Hard ceiling on total balance."),
    )
    lapse_unused_at_period_end = models.BooleanField(
        default=False,
        verbose_name=_("Lapse Unused at Period End"),
        help_text=_("CL=True (unused CL lapses Dec 31)."),
    )

    # ── Encashment ───────────────────────────────────────────────────
    is_encashable = models.BooleanField(
        default=False,
        verbose_name=_("Is Encashable"),
    )
    encashment_max_times_per_year = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Encashments Per Year"),
        help_text=_("EL=2. Applicable only while in service."),
    )
    encashment_min_days = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Min Days Per Encashment"),
        help_text=_("EL=10 days minimum per encashment request."),
    )
    encashment_min_balance_after = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Min Balance After Encashment"),
        help_text=_("EL=30 days must remain after encashment."),
    )
    encashable_on_separation = models.BooleanField(
        default=False,
        verbose_name=_("Encashable on Separation"),
        help_text=_("EL=True. SL=True (except misconduct termination)."),
    )
    encashment_triggers = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Encashment Triggers"),
        help_text=_(
            "List of triggers that allow encashment. "
            "e.g. ['separation','retirement','resignation','critical_health',"
            "'disability','marriage']. EL also allows 'in_service'."
        ),
    )
    no_encashment_on_misconduct = models.BooleanField(
        default=False,
        verbose_name=_("No Encashment on Misconduct Termination"),
        help_text=_("SL=True: encashment blocked if terminated for misconduct."),
    )

    # ── Advance Leave ────────────────────────────────────────────────
    allow_advance_leave = models.BooleanField(
        default=False,
        verbose_name=_("Allow Advance Leave"),
        help_text=_("EL=True: up to max_advance_leave_days in advance with CA approval."),
    )
    max_advance_leave_days = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Max Advance Leave Days"),
        help_text=_("EL=5 days advance."),
    )

    # ── Short Leave Specific ─────────────────────────────────────────
    max_short_leaves_per_month = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Short Leaves Per Month"),
        help_text=_("STL=2 per month."),
    )
    max_short_leave_hours_per_occasion = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Max Short Leave Hours Per Occasion"),
        help_text=_("STL=2 hours per occasion."),
    )

    # ── Paternity Specific ───────────────────────────────────────────
    paternity_days_before_birth = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Days Before Birth Allowed"),
        help_text=_("Paternity=7 days before expected delivery."),
    )
    paternity_days_after_birth = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Days After Birth Allowed"),
        help_text=_("Paternity=90 days (3 months) after birth."),
    )
    paternity_max_times_in_tenure = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Times in Tenure"),
        help_text=_("Paternity=2 times in entire tenure."),
    )

    # ── Audit ────────────────────────────────────────────────────────
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_policy_configs",
    )
    updated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_policy_configs",
    )

    # ─────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────

    def clean(self):
        # effective_to must be after effective_from
        if self.effective_to and self.effective_from:
            if self.effective_to <= self.effective_from:
                raise ValidationError(
                    _("effective_to must be after effective_from.")
                )

        # Only one active (effective_to=None) record per leave type
        if self.effective_to is None:
            qs = LeavePolicyConfig.objects.filter(
                leave_type=self.leave_type,
                effective_to__isnull=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    _(
                        "There is already an active (open-ended) policy for this "
                        "leave type. Close the existing one before creating a new active version."
                    )
                )

        # Encashment fields require is_encashable=True
        if not self.is_encashable:
            if self.encashment_max_times_per_year or self.encashment_min_days:
                raise ValidationError(
                    _("Encashment fields are only relevant when is_encashable=True.")
                )

        # Carry forward fields require allow_carry_forward=True
        if not self.allow_carry_forward and self.max_carry_forward_days:
            raise ValidationError(
                _("max_carry_forward_days is only relevant when allow_carry_forward=True.")
            )

        # Validate encashment_triggers values
        valid_triggers = {t.value for t in LeaveEncashmentTrigger}
        for trigger in self.encashment_triggers:
            if trigger not in valid_triggers:
                raise ValidationError(
                    _(f"Invalid encashment trigger: '{trigger}'. "
                      f"Valid values: {valid_triggers}")
                )

    # ─────────────────────────────────────────────
    # CLASS METHODS
    # ─────────────────────────────────────────────

    @classmethod
    def get_active_policy(cls, leave_type, reference_date=None):
        """
        Returns the LeavePolicyConfig version whose window covers reference_date.

        This is the SINGLE entry point used by LeavePolicyManager.
        All leave validation must call this — never read LeaveType fields directly.

        Grandfathered behavior:
            Pass reference_date = leave_application.startDate.date()
            to get the policy that was active WHEN the leave was applied,
            not today's policy.

        Fallback:
            Returns None if no config exists for this leave type yet
            (LeavePolicyManager then falls back to LeaveType legacy fields).
        """
        if reference_date is None:
            reference_date = timezone.now().date()

        return (
            cls.objects.filter(
                leave_type=leave_type,
                effective_from__lte=reference_date,
            )
            .filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=reference_date)
            )
            .order_by("-effective_from")
            .first()
        )

    @classmethod
    def close_current_policy(cls, leave_type, close_date):
        """
        Utility to close the currently active policy version.
        Call this BEFORE creating a new version.

        Usage:
            LeavePolicyConfig.close_current_policy(cl_leave_type, date(2026, 4, 1))
            LeavePolicyConfig.objects.create(
                leave_type=cl_leave_type,
                effective_from=date(2026, 4, 1),
                effective_to=None,
                ...new rules...
            )
        """
        active = cls.objects.filter(
            leave_type=leave_type,
            effective_to__isnull=True,
        ).first()
        if active:
            from datetime import timedelta
            active.effective_to = close_date - timedelta(days=1)
            active.save(update_fields=["effective_to"])

    # ─────────────────────────────────────────────
    # META
    # ─────────────────────────────────────────────

    def __str__(self):
        to = self.effective_to or "present"
        return f"{self.leave_type} | {self.effective_from} → {to}"

    class Meta:
        db_table  = "tbl_leave_policy_config"
        managed   = True
        verbose_name        = _("Leave Policy Config")
        verbose_name_plural = _("Leave Policy Configs")
        ordering  = ["-effective_from"]
        indexes   = [
            models.Index(
                fields=["leave_type", "effective_from"],
                name="idx_policy_config_type_date",
            )
        ]
        constraints = [
            # Prevent two open-ended configs for the same leave type at DB level
            models.UniqueConstraint(
                fields=["leave_type"],
                condition=Q(effective_to__isnull=True),
                name="unique_active_policy_per_leave_type",
            )
        ]