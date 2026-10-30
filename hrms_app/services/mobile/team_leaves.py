"""
Leave applications a reviewer (reporting manager / admin dept / superuser)
can see and act on - the mobile counterpart of the web tracker's
"Requested Leaves" and the status buttons on the leave detail page.
"""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils import timezone

from hrms_app.services import leave_approval
from hrms_app.services.leave_service import LeaveDomainService
from hrms_app.services.mobile.my_leaves import (
    PAGE_SIZE,
    STATUS_GROUPS,
    leave_detail,
    leave_item,
    leave_lock,
)


def _applicant(user, build_url):
    details = getattr(user, "personal_detail", None)
    avatar = getattr(details, "avatar", None)
    designation = getattr(details, "designation", None)
    return {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        # The web shows the username as the employee code.
        "employee_code": user.username,
        "designation": str(designation) if designation else None,
        "avatar_url": build_url(avatar.url) if avatar else None,
    }


# Statuses that are waiting for a decision (an approved leave can still be
# rejected on the web, but it isn't "waiting").
AWAITING = {settings.PENDING, settings.RECOMMEND, settings.PENDING_CANCELLATION}

LWP_CODE = "LWP"
DECIDE_ACTIONS = [(settings.APPROVED, "Approve"), (settings.REJECTED, "Reject")]
RECOMMEND_ACTIONS = [(settings.RECOMMEND, "Recommend"), (settings.REJECTED, "Reject")]
CANCEL_ACTION = (settings.CANCELLED, "Cancel Leave")


def team_item(reviewer, leave, build_url):
    return {
        **leave_item(reviewer, leave),
        "applicant": _applicant(leave.appliedBy, build_url),
        "needs_action": leave.status in AWAITING and bool(_open_actions(reviewer, leave)),
    }


def list_team_leaves(reviewer, *, status, year, search, page, build_url):
    """`status=pending` is the review queue; other groups browse history."""
    if status == "pending" or status is None:
        queryset = leave_approval.review_queue(reviewer)
    else:
        queryset = leave_approval.reviewable(reviewer).filter(startDate__year=year)
        if status in STATUS_GROUPS:
            queryset = queryset.filter(status__in=STATUS_GROUPS[status])

    if search:
        queryset = queryset.filter(
            Q(appliedBy__first_name__icontains=search)
            | Q(appliedBy__last_name__icontains=search)
            | Q(appliedBy__username__icontains=search)
        )
    queryset = queryset.select_related(
        "leave_type", "appliedBy__personal_detail__designation"
    ).order_by("-startDate")

    total = queryset.count()
    start = (max(page, 1) - 1) * PAGE_SIZE
    return {
        "results": [team_item(reviewer, leave, build_url) for leave in queryset[start : start + PAGE_SIZE]],
        "page": max(page, 1),
        "total": total,
        "has_next": start + PAGE_SIZE < total,
    }


def get_team_leave(reviewer, leave_id):
    return (
        leave_approval.reviewable(reviewer)
        .select_related(
            "leave_type",
            "appliedBy__personal_detail__designation",
            "appliedBy__reports_to__personal_detail__designation__department",
        )
        .filter(pk=leave_id)
        .first()
    )


def team_leave_detail(reviewer, leave, build_url):
    record = LeaveDomainService.get_balance_record(
        user=leave.appliedBy,
        leave_type=leave.leave_type,
        target_date=timezone.localtime(leave.startDate).date(),
    )
    actions = _open_actions(reviewer, leave)
    return {
        **leave_detail(reviewer, leave, build_url),
        "applicant": _applicant(leave.appliedBy, build_url),
        # The web detail page shows the applicant's balance to the reviewer.
        "applicant_balance": record.remaining_leave_balances if record else None,
        "allowed_actions": [{"status": value, "label": label} for value, label in actions],
        "waiting_note": None if actions else _waiting_note(leave),
    }


def _review_actions(reviewer, leave):
    """The mobile review rule (narrower than the web's status dropdown).

    Normal leave: pending -> Approve / Reject (reporting manager).
    LWP: pending -> Recommend / Reject (reporting manager), recommended ->
    Approve / Reject (admin department). An admin-department manager decides
    their own reportee's LWP directly.
    Any leave: pending cancellation -> Cancel Leave (reporting manager).
    Everything else, "not recommended" included, is final.
    """
    if leave.appliedBy_id == reviewer.pk:
        return []
    is_manager = leave.appliedBy.reports_to_id == reviewer.pk
    can_decide = is_manager or reviewer.is_superuser
    is_admin = reviewer.is_superuser or leave_approval.is_admin_department(reviewer)
    is_lwp = leave.leave_type.leave_type_short_code == LWP_CODE

    if leave.status == settings.PENDING_CANCELLATION:
        return [CANCEL_ACTION] if can_decide else []
    if is_lwp and leave.status == settings.RECOMMEND:
        return DECIDE_ACTIONS if is_admin else []
    if leave.status != settings.PENDING:
        return []
    if is_lwp and not (is_manager and is_admin):
        return RECOMMEND_ACTIONS if is_manager else []
    return DECIDE_ACTIONS if can_decide else []


def _open_actions(reviewer, leave):
    """Allowed review actions; none while the leave's period is locked."""
    if leave_lock(leave)["is_locked"]:
        return []
    return _review_actions(reviewer, leave)


def _waiting_note(leave):
    """Why an open application has no buttons for this reviewer."""
    return {
        settings.PENDING: "Waiting for the reporting manager's decision.",
        settings.RECOMMEND: "Recommended. Waiting for the Admin department's decision.",
        settings.PENDING_CANCELLATION: "Waiting for the reporting manager to cancel this leave.",
    }.get(leave.status)


def act(reviewer, leave, new_status, remark=""):
    """Returns None on success or an error message."""
    lock = leave_lock(leave)
    if lock["is_locked"]:
        return lock["lock_reason"]
    allowed = {value for value, _ in _review_actions(reviewer, leave)}
    if new_status not in allowed:
        return "This action is not allowed for this application."
    try:
        leave_approval.change_status(leave, new_status, reviewer, notes=(remark or "").strip())
    except ValidationError as exc:
        return exc.messages[0]
    except PermissionDenied as exc:  # the web's pre_save lock guard
        return str(exc)
    return None
