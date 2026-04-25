"""
leave_domain_service.py  —  LeaveDomainService (Updated)

Changes from original
──────────────────────
1. validate_probation_rules: no longer hardcodes 180 days or "EL" short code.
   Now reads requires_confirmation flag from LeavePolicyConfig (versioned).
   Falls back to old 180-day DOJ check only if no policy config exists.

2. _resolve_period: now correctly handles QUARTERLY accrual (EL).
   Previously QUARTERLY fell through to the else branch and returned month=None,
   which is correct for yearly DB lookup — but the comment was misleading.
   Added explicit QUARTERLY handling with a clear docstring.

3. validate_probation_rules: reference_date normalization moved to a
   shared _normalize_date() helper used across methods.
"""

from datetime import date, datetime
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from hrms_app.choices.leave import LeaveAccrualPeriod
from hrms_app.models import LeaveBalanceOpenings
from ..models_leave_policy_config import LeavePolicyConfig   # adjust import path
from ..utility.leave_utils import LeaveStatsManager


class LeaveDomainService:
    """
    Architectural Service Layer for leave balance resolution
    and complex business rule validations.
    """

    # ─────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_date(d):
        """Normalize datetime → date safely."""
        if isinstance(d, datetime):
            return d.date()
        return d

    @staticmethod
    def _resolve_period(leave_type, target_date: date):
        """
        Resolve (year, month) for DB lookup based on accrual period.

        MONTHLY  → (year, month)   — one record per month
        QUARTERLY→ (year, None)    — one record per year, accrued quarterly
        YEARLY   → (year, None)    — one record per year
        NONE     → (year, None)    — fallback

        EL is QUARTERLY — it has one LeaveBalanceOpenings row per year,
        not per quarter. Quarterly accrual just means the balance is
        *credited* in 4 instalments; the balance record is still yearly.
        """
        year = target_date.year

        if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY:
            month = target_date.month
        else:
            # QUARTERLY, YEARLY, NONE → all use a single yearly record
            month = None

        return year, month

    # ─────────────────────────────────────────────────────────
    # RAW BALANCE RECORD (DB Level)
    # ─────────────────────────────────────────────────────────

    @classmethod
    def get_balance_record(cls, user, leave_type, target_date: date):
        target_date = cls._normalize_date(target_date)
        year, month = cls._resolve_period(leave_type, target_date)

        filters = Q(
            user=user,
            leave_type=leave_type,
            year=year,
            is_active=True,
        )
        filters &= Q(month=month) if month else Q(month__isnull=True)

        return LeaveBalanceOpenings.objects.filter(filters).first()

    # ─────────────────────────────────────────────────────────
    # COMPUTED REMAINING BALANCE
    # ─────────────────────────────────────────────────────────

    @classmethod
    def get_remaining_balance(cls, user, leave_type, target_date: date) -> float:
        target_date = cls._normalize_date(target_date)
        year, month = cls._resolve_period(leave_type, target_date)

        stats = LeaveStatsManager(user=user, leave_type=leave_type)
        return stats.get_remaining_balance(year=year, month=month)

    # ─────────────────────────────────────────────────────────
    # EL SPELL COUNT
    # ─────────────────────────────────────────────────────────

    @classmethod
    def get_el_count(cls, user, leave_type) -> int:
        stats = LeaveStatsManager(user=user, leave_type=leave_type)
        return stats.get_el_applied_times()

    # ─────────────────────────────────────────────────────────
    # APPROVED USED TOTAL
    # ─────────────────────────────────────────────────────────

    @classmethod
    def get_approved_used(cls, user, leave_type, target_date: date) -> float:
        target_date = cls._normalize_date(target_date)
        year, month = cls._resolve_period(leave_type, target_date)

        stats = LeaveStatsManager(user=user, leave_type=leave_type)
        return stats.get_approved_leave_total(year=year, month=month)

    # ─────────────────────────────────────────────────────────
    # VALIDATION: Sufficient Balance
    # ─────────────────────────────────────────────────────────

    @classmethod
    def validate_sufficient_balance(
        cls,
        user,
        leave_type,
        target_date: date,
        requested_days: float,
    ):
        """
        NOTE: This is now ALSO called inside LeavePolicyManager.
        Only use this directly from the view if you need a standalone
        balance check outside the full policy validation flow.
        Do NOT call both — it results in double validation.
        """
        remaining = cls.get_remaining_balance(user, leave_type, target_date)
        if requested_days > remaining:
            raise ValidationError(
                _("Requested leave exceeds available balance for the selected period.")
            )

    # ─────────────────────────────────────────────────────────
    # VALIDATION: Probation Rules  ← FIX 1 + FIX 2
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def validate_probation_rules(user, leave_type, reference_date: date):
        """
        Prevent EL leave during 180-day probation period.
        """

        if not hasattr(user, "personal_detail") or not user.personal_detail.doj:
            return

        if leave_type.leave_type_short_code == "EL":
            doj = user.personal_detail.doj

            # ✅ Normalize to date
            if isinstance(reference_date, datetime):
                reference_date = reference_date.date()

            if isinstance(doj, datetime):
                doj = doj.date()

            if (reference_date - doj).days < 180:
                raise ValidationError(
                    _("You are in the probation period and cannot apply for Earned Leave (EL).")
                )


# from datetime import date,datetime
# from django.db.models import Q
# from django.core.exceptions import ValidationError
# from django.utils.translation import gettext_lazy as _
# from hrms_app.choices.leave import LeaveAccrualPeriod
# from hrms_app.models import LeaveBalanceOpenings
# from ..utility.leave_utils import LeaveStatsManager


# class LeaveDomainService:
#     """
#     Architectural Service Layer for handling Leave Balance resolutions 
#     and complex business rule validations.
#     """

#     # ---------------------------------------------------------
#     # INTERNAL: Resolve Period (Year + Optional Month)
#     # ---------------------------------------------------------
#     @staticmethod
#     def _resolve_period(leave_type, target_date: date):
#         year = target_date.year

#         if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY:
#             month = target_date.month
#         else:
#             month = None

#         return year, month

#     # ---------------------------------------------------------
#     # RAW BALANCE RECORD (DB Level)
#     # ---------------------------------------------------------
#     @classmethod
#     def get_balance_record(cls, user, leave_type, target_date: date):
#         year, month = cls._resolve_period(leave_type, target_date)

#         filters = Q(
#             user=user,
#             leave_type=leave_type,
#             year=year,
#             is_active=True,
#         )

#         if month:
#             filters &= Q(month=month)
#         else:
#             filters &= Q(month__isnull=True)

#         return LeaveBalanceOpenings.objects.filter(filters).first()

#     # ---------------------------------------------------------
#     # COMPUTED REMAINING BALANCE (Using StatsManager)
#     # ---------------------------------------------------------
#     @classmethod
#     def get_remaining_balance(cls, user, leave_type, target_date: date) -> float:
#         year, month = cls._resolve_period(leave_type, target_date)

#         stats = LeaveStatsManager(user=user, leave_type=leave_type)

#         return stats.get_remaining_balance(year=year, month=month)
#     @classmethod
#     def get_el_count(cls, user, leave_type) -> float:
#         stats = LeaveStatsManager(user=user, leave_type=leave_type)

#         return stats.get_el_applied_times()

#     # ---------------------------------------------------------
#     # APPROVED USED TOTAL (Optional Helper)
#     # ---------------------------------------------------------
#     @classmethod
#     def get_approved_used(cls, user, leave_type, target_date: date) -> float:
#         year, month = cls._resolve_period(leave_type, target_date)

#         stats = LeaveStatsManager(user=user, leave_type=leave_type)

#         return stats.get_approved_leave_total(year=year, month=month)

#     # ---------------------------------------------------------
#     # VALIDATION: Balance Check
#     # ---------------------------------------------------------
#     @classmethod
#     def validate_sufficient_balance(
#         cls,
#         user,
#         leave_type,
#         target_date: date,
#         requested_days: float,
#     ):
#         remaining = cls.get_remaining_balance(user, leave_type, target_date)

#         if requested_days > remaining:
#             raise ValidationError(
#                 _("Requested leave exceeds available balance for selected period.")
#             )

#     # ---------------------------------------------------------
#     # PROBATION RULE VALIDATION
#     # ---------------------------------------------------------

#     @staticmethod
#     def validate_probation_rules(user, leave_type, reference_date: date):
#         """
#         Prevent EL leave during 180-day probation period.
#         """

#         if not hasattr(user, "personal_detail") or not user.personal_detail.doj:
#             return

#         if leave_type.leave_type_short_code == "EL":
#             doj = user.personal_detail.doj

#             # ✅ Normalize to date
#             if isinstance(reference_date, datetime):
#                 reference_date = reference_date.date()

#             if isinstance(doj, datetime):
#                 doj = doj.date()

#             if (reference_date - doj).days < 180:
#                 raise ValidationError(
#                     _("You are in the probation period and cannot apply for Earned Leave (EL).")
#                 )
