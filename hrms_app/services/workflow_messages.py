"""
What the employee and their manager are told about a leave or tour. Every
event reaches both, each in their own words; in-app notifications, pushes and
emails all use these texts.
"""
from django.conf import settings

_DECISIONS = {
    settings.APPROVED: "approved",
    settings.REJECTED: "rejected",
    settings.CANCELLED: "cancelled",
    settings.COMPLETED: "marked as completed",
    settings.EXTENDED: "extended",
}


def _name(user):
    return user.get_full_name() or user.username


def leave_label(leave):
    return f"leave application '{leave.applicationNo}'"


def tour_label(tour):
    return f"tour {tour.from_destination} → {tour.to_destination}"


def admin_recommendation_text(label, applicant, actor=None):
    """For the admin department, who decide a recommended LWP."""
    recommender = actor or applicant.reports_to
    by_whom = f" by {_name(recommender)}" if recommender else ""
    return f"{_name(applicant)}'s {label} has been recommended{by_whom}. Please approve or reject it."


def build_messages(status, label, applicant, *, actor=None, rerequested=False):
    """(employee text, manager text) for ``status``.

    ``label`` names the record: "leave application EL/123", "tour A → B".
    ``actor`` is who decided, when that may not be the manager (admin
    department, superuser).
    """
    manager = applicant.reports_to
    employee = _name(applicant)
    manager_name = _name(manager) if manager else "your manager"
    by_manager = actor is None or manager is None or actor.pk == manager.pk
    decided_by = manager_name if by_manager else _name(actor)

    if rerequested:
        return (
            f"Your updated {label} has been sent to {manager_name} for approval.",
            f"{employee} changed the schedule of {label} and requested your approval again.",
        )
    if status == settings.PENDING:
        return (
            f"Your {label} has been submitted to {manager_name} for approval.",
            f"{employee} has submitted {label}. Please review it.",
        )
    if status == settings.PENDING_CANCELLATION:
        return (
            f"Your cancellation request for {label} has been sent to {manager_name}.",
            f"{employee} has requested to cancel {label}. Please review it.",
        )
    if status == settings.RECOMMEND:
        return (
            f"Your {label} has been recommended by {decided_by} and sent to the Admin department.",
            f"You recommended {employee}'s {label}. It is now with the Admin department."
            if by_manager
            else f"{employee}'s {label} has been recommended by {decided_by}.",
        )

    if status == settings.NOT_RECOMMEND:
        return (
            f"Your {label} was not recommended by {decided_by}.",
            f"You did not recommend {employee}'s {label}."
            if by_manager
            else f"{employee}'s {label} was not recommended by {decided_by}.",
        )

    done = _DECISIONS.get(status, status.replace("_", " "))
    return (
        f"Your {label} has been {done} by {decided_by}.",
        f"You {done} {employee}'s {label}."
        if by_manager and status in (settings.APPROVED, settings.REJECTED, settings.CANCELLED)
        else f"{employee}'s {label} has been {done} by {decided_by}.",
    )
