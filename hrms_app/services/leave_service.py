from datetime import date
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from hrms_app.choices.leave import LeaveAccrualPeriod
from hrms_app.models import LeaveBalanceOpenings
from ..utility.leave_utils import LeaveStatsManager


class LeaveDomainService:
    """
    Architectural Service Layer for handling Leave Balance resolutions 
    and complex business rule validations.
    """

    # ---------------------------------------------------------
    # INTERNAL: Resolve Period (Year + Optional Month)
    # ---------------------------------------------------------
    @staticmethod
    def _resolve_period(leave_type, target_date: date):
        year = target_date.year

        if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY:
            month = target_date.month
        else:
            month = None

        return year, month

    # ---------------------------------------------------------
    # RAW BALANCE RECORD (DB Level)
    # ---------------------------------------------------------
    @classmethod
    def get_balance_record(cls, user, leave_type, target_date: date):
        year, month = cls._resolve_period(leave_type, target_date)

        filters = Q(
            user=user,
            leave_type=leave_type,
            year=year,
            is_active=True,
        )

        if month:
            filters &= Q(month=month)
        else:
            filters &= Q(month__isnull=True)

        return LeaveBalanceOpenings.objects.filter(filters).first()

    # ---------------------------------------------------------
    # COMPUTED REMAINING BALANCE (Using StatsManager)
    # ---------------------------------------------------------
    @classmethod
    def get_remaining_balance(cls, user, leave_type, target_date: date) -> float:
        year, month = cls._resolve_period(leave_type, target_date)

        stats = LeaveStatsManager(user=user, leave_type=leave_type)

        return stats.get_remaining_balance(year=year, month=month)
    @classmethod
    def get_el_count(cls, user, leave_type) -> float:
        stats = LeaveStatsManager(user=user, leave_type=leave_type)

        return stats.get_el_applied_times()

    # ---------------------------------------------------------
    # APPROVED USED TOTAL (Optional Helper)
    # ---------------------------------------------------------
    @classmethod
    def get_approved_used(cls, user, leave_type, target_date: date) -> float:
        year, month = cls._resolve_period(leave_type, target_date)

        stats = LeaveStatsManager(user=user, leave_type=leave_type)

        return stats.get_approved_leave_total(year=year, month=month)

    # ---------------------------------------------------------
    # VALIDATION: Balance Check
    # ---------------------------------------------------------
    @classmethod
    def validate_sufficient_balance(
        cls,
        user,
        leave_type,
        target_date: date,
        requested_days: float,
    ):
        remaining = cls.get_remaining_balance(user, leave_type, target_date)

        if requested_days > remaining:
            raise ValidationError(
                _("Requested leave exceeds available balance for selected period.")
            )

    # ---------------------------------------------------------
    # PROBATION RULE VALIDATION
    # ---------------------------------------------------------
    @staticmethod
    def validate_probation_rules(user, leave_type, reference_date: date):

        if not hasattr(user, "personal_detail") or not user.personal_detail.doj:
            return

        if leave_type.leave_type_short_code == "EL":
            doj = user.personal_detail.doj

            if (reference_date - doj).days < 180:
                raise ValidationError(
                    _(
                        "You are in the probation period and cannot apply for Earned Leave (EL)."
                    )
                )
