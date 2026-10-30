"""
Dashboard leave balances, shared by the web dashboard (``get_leave_balances``
template tag) and the mobile ``home/summary`` API.

- Yearly leave  -> balance row with year=current_year AND month=None
- Monthly leave -> balance row with year=current_year AND month=current_month
- available     -> remaining_leave_balances - pending (on hold) applications
"""
from django.conf import settings
from django.db.models import Sum
from django.urls import reverse
from django.utils.timezone import now

from hrms_app.choices.leave import LeaveAccrualPeriod
from hrms_app.models import LeaveApplication, LeaveBalanceOpenings, LeaveType


def _sum_used(user, leave_type, status, date_filter):
    return (
        LeaveApplication.objects.filter(
            appliedBy=user,
            leave_type=leave_type,
            status=status,
            **date_filter,
        ).aggregate(Sum("usedLeave"))["usedLeave__sum"]
        or 0
    )


def get_dashboard_leave_balances(user):
    """Returns one dict per leave type the user has a balance row for."""
    today = now().date()
    current_year = today.year
    current_month = today.month

    leave_balances_list = []
    user_balances = LeaveBalanceOpenings.objects.filter(user=user, year=current_year)

    for leave_type in LeaveType.objects.all():
        if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY:
            balance = user_balances.filter(leave_type=leave_type, month=current_month).first()
            date_filter = {"endDate__year": current_year, "endDate__month": current_month}
        else:
            balance = user_balances.filter(leave_type=leave_type, month__isnull=True).first()
            date_filter = {"endDate__year": current_year}

        if not balance:
            continue

        used_leave = _sum_used(user, leave_type, settings.APPROVED, date_filter)
        on_hold_leave = _sum_used(user, leave_type, settings.PENDING, date_filter)

        if leave_type.leave_type_short_code == "STL":
            apply_url = reverse("short_leave_create")
        else:
            apply_url = reverse("apply_leave_with_id", args=[leave_type.pk])

        leave_balances_list.append(
            {
                "pk": balance.pk,
                "balance": balance.remaining_leave_balances,
                "used_leave": used_leave,
                "on_hold": on_hold_leave,
                "total_balance": balance.remaining_leave_balances - on_hold_leave,
                "is_active": balance.is_active,
                "leave_type": leave_type,
                "url": apply_url,
                "color": leave_type.color_hex,
            }
        )

    # Female-only ML logic (yearly based)
    personal = getattr(user, "personal_detail", None)
    if personal and personal.gender and personal.gender.gender == "Female":
        ml_balance = user_balances.filter(
            leave_type__leave_type_short_code=settings.ML,
            month__isnull=True,
        ).first()

        if ml_balance:
            year_filter = {"endDate__year": current_year}
            used_leave = _sum_used(user, ml_balance.leave_type, settings.APPROVED, year_filter)
            on_hold_leave = _sum_used(user, ml_balance.leave_type, settings.PENDING, year_filter)

            leave_balances_list.append(
                {
                    "pk": ml_balance.pk,
                    "balance": ml_balance.remaining_leave_balances,
                    "used_leave": used_leave,
                    "on_hold": on_hold_leave,
                    "total_balance": ml_balance.remaining_leave_balances - on_hold_leave,
                    "is_active": ml_balance.is_active,
                    "leave_type": ml_balance.leave_type,
                    "url": reverse("apply_leave_with_id", args=[ml_balance.leave_type.pk]),
                    "color": "#ff9447",
                }
            )

    return leave_balances_list
