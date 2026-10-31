"""
The employee's own leave applications for the mobile Leaves tab.

Actions mirror the web detail page (leave_application_detail.html):
- approved                      -> "Cancel request" (status -> pending_cancellation;
                                   the manager then cancels and the balance is restored)
- pending / cancelled / rejected -> Edit, Delete
"""
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from hrms_app.models import LeaveApplication, LeaveLog
from hrms_app.services import attendance_lock
from hrms_app.services.leave_service import LeaveDomainService
from hrms_app.services.mobile.formatters import employee_code_label, hhmm, iso_date
from hrms_app.services.mobile.formatters import plain_text as _plain
from hrms_app.services.mobile.home_summary import comp_off_payload, leave_balances_payload
from hrms_app.services.mobile.leave_apply import applied_leave_days

PAGE_SIZE = 20
CANCELLABLE = {settings.APPROVED}
EDITABLE = {settings.PENDING, settings.CANCELLED, settings.REJECTED}
CHANGE_PERMISSION = "hrms_app.change_leaveapplication"
DELETE_PERMISSION = "hrms_app.delete_leaveapplication"

# Status filter values the app sends -> statuses they cover.
STATUS_GROUPS = {
    "pending": [settings.PENDING, settings.RECOMMEND, settings.NOT_RECOMMEND],
    "approved": [settings.APPROVED],
    "rejected": [settings.REJECTED],
    "cancelled": [settings.CANCELLED, settings.PENDING_CANCELLATION],
}


def _local_date(dt):
    return timezone.localtime(dt).date() if dt else None


def leave_lock(leave):
    """Lock info for the leave's whole date range (audit freeze)."""
    return attendance_lock.lock_info(leave.startDate, leave.endDate)


def _actions(user, leave, lock=None):
    """What the applicant may do. Nothing is allowed on a locked period."""
    lock = lock or leave_lock(leave)
    open_ = leave.appliedBy_id == user.pk and not lock["is_locked"]
    return {
        "can_cancel": open_ and leave.status in CANCELLABLE and user.has_perm(CHANGE_PERMISSION),
        "can_edit": open_ and leave.status in EDITABLE and user.has_perm(CHANGE_PERMISSION),
        "can_delete": open_ and leave.status in EDITABLE and user.has_perm(DELETE_PERMISSION),
    }


def leave_item(user, leave):
    leave_type = leave.leave_type
    reason = _plain(leave.reason)
    lock = leave_lock(leave)
    return {
        "id": leave.pk,
        "application_no": leave.applicationNo,
        "leave_type": {
            "id": leave_type.pk,
            "name": leave_type.leave_type,
            "code": leave_type.leave_type_short_code,
            "color": leave_type.color_hex,
        },
        "start_date": iso_date(_local_date(leave.startDate)),
        "end_date": iso_date(_local_date(leave.endDate)),
        "start_day_choice": leave.startDayChoice,
        "start_day_display": leave.get_startDayChoice_display(),
        "end_day_choice": leave.endDayChoice,
        "end_day_display": leave.get_endDayChoice_display(),
        "used_leave": leave.usedLeave,
        "is_short_leave": leave.is_short_leave(),
        "from_time": hhmm(leave.from_time),
        "to_time": hhmm(leave.to_time),
        "status": leave.status,
        "status_display": leave.get_status_display(),
        "applied_on": timezone.localtime(leave.applyingDate).isoformat(),
        "reason_preview": reason[:120],
        **lock,
        **_actions(user, leave, lock),
    }


def _my_leaves(user, year):
    return (
        LeaveApplication.objects.filter(appliedBy=user, startDate__year=year)
        .select_related("leave_type")
        .order_by("-startDate")
    )


def get_overview(user, year):
    """Balances (current period, same as the web cards) + this year's counts."""
    counts = _my_leaves(user, year).aggregate(
        total=Count("id"),
        days_taken=Sum("usedLeave", filter=Q(status=settings.APPROVED)),
        **{group: Count("id", filter=Q(status__in=statuses)) for group, statuses in STATUS_GROUPS.items()},
    )
    manager = user.reports_to
    return {
        "year": year,
        # Same for every application (the employee's reporting manager).
        "approver": (manager.get_full_name() or manager.username) if manager else None,
        "balances": leave_balances_payload(user),
        "comp_off": comp_off_payload(user, timezone.localdate()),
        "counts": {group: counts[group] for group in STATUS_GROUPS} | {"total": counts["total"]},
        "days_taken": counts["days_taken"] or 0,
    }


def list_leaves(user, *, year, status=None, leave_type=None, page=1):
    queryset = _my_leaves(user, year)
    if status in STATUS_GROUPS:
        queryset = queryset.filter(status__in=STATUS_GROUPS[status])
    if leave_type:
        queryset = queryset.filter(leave_type_id=leave_type)

    total = queryset.count()
    start = (max(page, 1) - 1) * PAGE_SIZE
    rows = list(queryset[start : start + PAGE_SIZE])
    return {
        "results": [leave_item(user, leave) for leave in rows],
        "page": max(page, 1),
        "total": total,
        "has_next": start + PAGE_SIZE < total,
    }


def get_leave(user, leave_id):
    return (
        LeaveApplication.objects.select_related(
            "leave_type",
            "appliedBy__reports_to__personal_detail__designation__department",
        )
        .filter(pk=leave_id, appliedBy=user)
        .first()
    )


def _person(user):
    """Name + designation / department / code for the reporting-authority card."""
    if user is None:
        return None
    details = getattr(user, "personal_detail", None)
    designation = getattr(details, "designation", None)
    return {
        "name": user.get_full_name() or user.username,
        "designation": str(designation) if designation else None,
        "department": str(designation.department) if designation and designation.department_id else None,
        "employee_code": employee_code_label(getattr(details, "employee_code", None)),
    }


def leave_detail(user, leave, build_url):
    data = leave_item(user, leave)
    data.update(
        {
            "reason": _plain(leave.reason),
            "leave_address": leave.leave_address,
            "attachment_url": build_url(leave.attachment.url) if leave.attachment else None,
            "attachment_name": leave.attachment.name.rsplit("/", 1)[-1] if leave.attachment else None,
            "approver": _person(leave.appliedBy.reports_to),
            # The web shows the type's balance while a request is pending -
            # always the applicant's (a reviewer opens this via team_leaves).
            "available_balance": (
                LeaveDomainService.get_remaining_balance(
                    user=leave.appliedBy,
                    leave_type=leave.leave_type,
                    target_date=_local_date(leave.startDate),
                )
                if leave.status == settings.PENDING
                else None
            ),
            "days": applied_leave_days(leave),
            "logs": [
                {
                    "action": log.action,
                    "by": log.action_by_name,
                    "at": timezone.localtime(log.timestamp).isoformat(),
                    "notes": _plain(log.notes),
                }
                for log in leave.logs.order_by("timestamp")
            ],
        }
    )
    return data


def _refusal(leave, action, not_allowed):
    """Why `action` can't be done: the lock message wins, else `not_allowed`."""
    lock = leave_lock(leave)
    if lock["is_locked"]:
        return lock["lock_reason"]
    return not_allowed


@transaction.atomic
def request_cancellation(user, leave):
    """Approved -> pending_cancellation, logged like the web status form.
    Returns None on success, else the reason it was refused."""
    if not _actions(user, leave)["can_cancel"]:
        return _refusal(leave, "cancel", "Only approved leave can be cancelled.")
    leave.status = settings.PENDING_CANCELLATION
    leave.save()  # signals notify the manager
    LeaveLog.create_log(leave, user, leave.status)
    return None


def delete_leave(user, leave):
    """Returns None on success, else the reason it was refused."""
    if not _actions(user, leave)["can_delete"]:
        return _refusal(
            leave, "delete", "Only pending, rejected or cancelled applications can be deleted."
        )
    leave.delete()
    return None
