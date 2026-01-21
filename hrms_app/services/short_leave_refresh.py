from django.db import transaction
from django.utils import timezone
from ..models import LeaveType, LeaveBalanceOpenings,CustomUser


def refresh_monthly_short_leave(system_user=None):
    """
    Refresh monthly Short Leave balances (SLT).
    """
    today = timezone.now().date()
    year = today.year

    short_leave_types = LeaveType.objects.filter(
        accrual_period="MONTHLY",
        expiry_policy="PERIOD_END",
        must_apply_within_accrual_period=True,
        leave_unit__in=["HOUR", "MINUTE"],
    )

    users = CustomUser.objects.filter(is_active=True)

    with transaction.atomic():
        for leave_type in short_leave_types:
            for user in users:
                balance, created = LeaveBalanceOpenings.objects.get_or_create(
                    user=user,
                    leave_type=leave_type,
                    year=year,
                    defaults={
                        "opening_balance": leave_type.accrual_quantity,
                        "remaining_leave_balances": leave_type.accrual_quantity,
                        "no_of_leaves": leave_type.accrual_quantity,
                        "created_by": system_user,
                    },
                )

                # If already exists → RESET (monthly expiry)
                if not created:
                    balance.opening_balance = leave_type.accrual_quantity
                    balance.remaining_leave_balances = leave_type.accrual_quantity
                    balance.no_of_leaves = leave_type.accrual_quantity
                    balance.updated_by = system_user
                    balance.save(
                        update_fields=[
                            "opening_balance",
                            "remaining_leave_balances",
                            "no_of_leaves",
                            "updated_by",
                            "updated_at",
                        ]
                    )
