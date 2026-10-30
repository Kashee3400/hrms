"""
Leave review (approve / reject / recommend / cancel) shared by the web
detail page and the mobile API.

Rules come from the web:
- who reviews        : the applicant's reporting manager, the "admin"
                       department, superusers (LeaveApplicationDetailView)
- which actions      : LeaveStatusUpdateForm.get_filtered_choices
- the review queue   : utility.leave_utils.get_employee_requested_leave
- balance effect     : approve deducts, reject/cancel of an approved leave restores
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import localtime

from hrms_app.choices.leave import LeaveAccrualPeriod
from hrms_app.hrms.form import LeaveStatusUpdateForm
from hrms_app.models import LeaveApplication, LeaveBalanceOpenings, LeaveLog

ADMIN_DEPARTMENT = "admin"


def is_admin_department(user):
    details = getattr(user, "personal_detail", None)
    designation = getattr(details, "designation", None)
    department = getattr(designation, "department", None)
    return getattr(department, "department", None) == ADMIN_DEPARTMENT


def is_leave_reviewer(user):
    """Has someone to review: reporting manager (has employees), admin dept, superuser."""
    return user.is_superuser or user.employees.exists() or is_admin_department(user)


def review_queue(user):
    """Applications waiting for this user's decision (same as the web tracker)."""
    if user.is_superuser:
        return LeaveApplication.objects.filter(
            status__in=[settings.PENDING, settings.RECOMMEND, settings.PENDING_CANCELLATION]
        ).exclude(appliedBy=user)

    queue = Q(
        appliedBy__in=user.employees.all(),
        status__in=[settings.PENDING, settings.PENDING_CANCELLATION],
    )
    if is_admin_department(user):
        # LWP recommended by a manager waits for the admin department.
        queue |= Q(status=settings.RECOMMEND)
    return LeaveApplication.objects.filter(queue).exclude(appliedBy=user)


def reviewable(user):
    """Every application this user may open as a reviewer (any status)."""
    if user.is_superuser or user.is_staff or is_admin_department(user):
        return LeaveApplication.objects.exclude(appliedBy=user)
    return LeaveApplication.objects.filter(appliedBy__in=user.employees.all())


def allowed_statuses(user, leave):
    """[(status, label)] the reviewer may set now; excludes the current status."""
    if leave.appliedBy_id == user.pk:
        return []
    try:
        choices = LeaveStatusUpdateForm(user=user, instance=leave).fields["status"].widget.choices
    except AttributeError:  # reviewer without designation/department
        return []
    return [(value, label) for value, label in choices if value and value != leave.status]


# ─────────────────────────────────────────────────────────────
# Status change + balance (moved from LeaveApplicationUpdateView)
# ─────────────────────────────────────────────────────────────


def _update_leave_balance(leave_application, old_status):
    if old_status == leave_application.status:
        return

    leave_type = leave_application.leave_type
    leave_date = localtime(leave_application.startDate)
    month = leave_date.month if leave_type.accrual_period == LeaveAccrualPeriod.MONTHLY else None

    leave_balance = LeaveBalanceOpenings.objects.select_for_update().filter(
        user=leave_application.appliedBy,
        leave_type=leave_type,
        year=leave_date.year,
        month=month,
    ).first()
    if not leave_balance:
        raise ValidationError("Leave balance record not found.")

    # APPROVE -> deduct
    if (
        leave_application.status == settings.APPROVED
        and old_status
        in [
            settings.PENDING,
            settings.RECOMMEND,
            settings.NOT_RECOMMEND,
            settings.PENDING_CANCELLATION,
            settings.REJECTED,
            settings.CANCELLED,
        ]
        and not leave_application.is_leave_deducted
    ):
        if leave_balance.remaining_leave_balances < leave_application.usedLeave:
            raise ValidationError("Insufficient leave balance.")
        leave_balance.remaining_leave_balances -= leave_application.usedLeave
        leave_balance.used += leave_application.usedLeave
        leave_application.is_leave_deducted = True

    # REJECT / CANCEL of an approved leave -> restore
    elif (
        leave_application.status in [settings.REJECTED, settings.CANCELLED]
        and old_status in [settings.APPROVED, settings.PENDING_CANCELLATION]
        and leave_application.is_leave_deducted
    ):
        leave_balance.remaining_leave_balances += leave_application.usedLeave
        leave_balance.used -= leave_application.usedLeave
        leave_application.is_leave_deducted = False

    leave_balance.closing_balance = leave_balance.remaining_leave_balances
    leave_balance.save(update_fields=["remaining_leave_balances", "used", "closing_balance"])
    leave_application.save(update_fields=["is_leave_deducted"])


@transaction.atomic
def change_status(leave, new_status, actor, notes=""):
    """Sets the status, applies the balance effect and logs it - all or nothing.

    Raises ValidationError (e.g. insufficient balance) and rolls back, so the
    status is never saved without its balance change.
    """
    old_status = (
        LeaveApplication.objects.select_for_update()
        .filter(pk=leave.pk)
        .values_list("status", flat=True)
        .first()
    )
    leave.status = new_status
    leave.save()  # signals notify the applicant / manager
    _update_leave_balance(leave, old_status)
    LeaveLog.create_log(leave, actor, new_status, notes=notes or "")
    return leave
