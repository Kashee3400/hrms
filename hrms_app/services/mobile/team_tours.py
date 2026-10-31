"""
Tours a reviewer can see and act on in the app.

Rule (same idea as team_leaves): the reporting manager decides.
pending / extended   -> Approve / Reject
pending cancellation -> Cancel Tour
Everything else is final, so it has no buttons.
"""
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from hrms_app.services import tour_approval
from hrms_app.services.mobile.team_leaves import _applicant
from hrms_app.services.mobile.team_out import team_out
from hrms_app.services.mobile.tours import PAGE_SIZE, STATUS_GROUPS, tour_detail, tour_item, tour_lock

DECIDE_ACTIONS = [(settings.APPROVED, "Approve"), (settings.REJECTED, "Reject")]
CANCEL_ACTION = (settings.CANCELLED, "Cancel Tour")
WITH_APPLICANT = ("applied_by__personal_detail__designation", "applied_by__reports_to")


def _review_actions(reviewer, tour):
    if tour.applied_by_id == reviewer.pk:
        return []
    if tour.applied_by.reports_to_id != reviewer.pk and not reviewer.is_superuser:
        return []
    if tour.status == settings.PENDING_CANCELLATION:
        return [CANCEL_ACTION]
    if tour.status in (settings.PENDING, settings.EXTENDED):
        return DECIDE_ACTIONS
    return []


def _open_actions(reviewer, tour):
    """Allowed review actions; none while the tour's period is locked."""
    if tour_lock(tour)["is_locked"]:
        return []
    return _review_actions(reviewer, tour)


def team_item(reviewer, tour, build_url):
    return {
        **tour_item(reviewer, tour),
        "applicant": _applicant(tour.applied_by, build_url),
        "needs_action": bool(_open_actions(reviewer, tour)),
    }


def list_team_tours(reviewer, *, status, year, search, page, build_url):
    """`status=pending` is the review queue; other groups browse history."""
    if status == "pending" or status is None:
        queryset = tour_approval.review_queue(reviewer)
    else:
        queryset = tour_approval.reviewable(reviewer).filter(start_date__year=year)
        if status in STATUS_GROUPS:
            queryset = queryset.filter(status__in=STATUS_GROUPS[status])

    if search:
        queryset = queryset.filter(
            Q(applied_by__first_name__icontains=search)
            | Q(applied_by__last_name__icontains=search)
            | Q(applied_by__username__icontains=search)
            | Q(from_destination__icontains=search)
            | Q(to_destination__icontains=search)
        )
    queryset = queryset.select_related(*WITH_APPLICANT).order_by("-start_date", "-pk")

    total = queryset.count()
    start = (max(page, 1) - 1) * PAGE_SIZE
    return {
        "results": [team_item(reviewer, tour, build_url) for tour in queryset[start : start + PAGE_SIZE]],
        "page": max(page, 1),
        "total": total,
        "has_next": start + PAGE_SIZE < total,
    }


def get_team_tour(reviewer, tour_id):
    return tour_approval.reviewable(reviewer).select_related(*WITH_APPLICANT).filter(pk=tour_id).first()


def team_tour_detail(reviewer, tour, build_url):
    actions = _open_actions(reviewer, tour)
    waiting = tour.status in tour_approval.AWAITING and not tour_lock(tour)["is_locked"]
    return {
        **tour_detail(reviewer, tour, build_url),
        "applicant": _applicant(tour.applied_by, build_url),
        "allowed_actions": [{"status": value, "label": label} for value, label in actions],
        "waiting_note": (
            "Waiting for the reporting manager's decision." if waiting and not actions else None
        ),
        "team_out": (
            team_out(reviewer, tour.applied_by, tour.start_date, tour.extended_end_date or tour.end_date)
            if tour.status in (settings.PENDING, settings.EXTENDED)
            else None
        ),
    }


def act(reviewer, tour, new_status, remark=""):
    """Returns None on success or an error message."""
    lock = tour_lock(tour)
    if lock["is_locked"]:
        return lock["lock_reason"]
    if new_status not in {value for value, _ in _review_actions(reviewer, tour)}:
        return "This action is not allowed for this tour."
    remark = (remark or "").strip()
    if new_status == settings.REJECTED and not remark:
        return "Reason is required when rejecting a tour."

    decide = {
        settings.APPROVED: tour.approve,
        settings.REJECTED: tour.reject,
        settings.CANCELLED: tour.cancel,
    }[new_status]
    tour._actor = reviewer  # the signals name them in the messages
    try:
        with transaction.atomic():
            decide(action_by=reviewer, reason=remark)
    except PermissionDenied as exc:  # the web's pre_save lock guard
        return str(exc)
    return None
