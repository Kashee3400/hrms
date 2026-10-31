"""
Daily reminder of what is waiting for a reviewer's decision: one message per
reviewer per working day, counting only requests they can still act on.

A reviewer has no apply limit to meet; what stops them is the attendance lock.
So this nudges by age, and a locked request drops out. It stays off until
APPROVAL_REMINDER_DAYS is set above 0 in Application Settings.
"""
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from hrms_app.models import LeaveApplication, Notification, UserTour
from hrms_app.services import leave_approval, tour_approval
from hrms_app.services.attendance_gaps import _is_working_day, _notify, _setting
from hrms_app.services.mobile import team_leaves, team_tours
from hrms_app.services.notification_push import APPROVALS_ROUTE, APPROVALS_TOURS_ROUTE

REMINDER_DAYS_KEY = "APPROVAL_REMINDER_DAYS"


def reminder_days():
    try:
        return max(int(_setting(REMINDER_DAYS_KEY)), 0)
    except ValueError:
        return 0


def _has_waited(since, today, days):
    """At least ``days`` working days have passed since ``since``."""
    day, count = timezone.localtime(since).date(), 0
    while day < today:
        day += timedelta(days=1)
        count += _is_working_day(day)
        if count >= days:
            return True
    return False


def _manager(user):
    manager = user.reports_to
    return [manager] if manager and manager.is_active else []


def _leave_reviewers(leave):
    """A recommended LWP waits for the admin department, anything else for the manager."""
    if leave.status == settings.RECOMMEND:
        return leave_approval.admin_department_users()
    return _manager(leave.appliedBy)


def _message(leaves, tours):
    parts = []
    if leaves:
        parts.append(f"{leaves} leave request{'s' if leaves != 1 else ''}")
    if tours:
        parts.append(f"{tours} tour request{'s' if tours != 1 else ''}")
    return f"{' and '.join(parts)} waiting for your decision. Please review them in the HRMS app."


def _sent_today(reviewer, today):
    return Notification.objects.filter(
        receiver=reviewer,
        go_route_mobile__in=[APPROVALS_ROUTE, APPROVALS_TOURS_ROUTE],
        timestamp__date=today,
    ).exists()


def send_approval_reminders(today=None):
    """Returns how many reviewers were reminded. Safe to run twice in a day."""
    today = today or timezone.localdate()
    days = reminder_days()
    if not days or not _is_working_day(today):
        return 0

    waiting = defaultdict(lambda: {"reviewer": None, "leaves": 0, "tours": 0})

    leaves = LeaveApplication.objects.filter(
        status__in=[settings.PENDING, settings.RECOMMEND, settings.PENDING_CANCELLATION],
        appliedBy__is_active=True,
    ).select_related("appliedBy__reports_to", "leave_type")
    for leave in leaves:
        if not _has_waited(leave.updatedAt, today, days):
            continue
        for reviewer in _leave_reviewers(leave):
            if team_leaves._open_actions(reviewer, leave):
                waiting[reviewer.pk]["reviewer"] = reviewer
                waiting[reviewer.pk]["leaves"] += 1

    tours = UserTour.objects.filter(
        status__in=tour_approval.AWAITING, applied_by__is_active=True
    ).select_related("applied_by__reports_to")
    for tour in tours:
        if not _has_waited(tour.updated_at, today, days):
            continue
        for reviewer in _manager(tour.applied_by):
            if team_tours._open_actions(reviewer, tour):
                waiting[reviewer.pk]["reviewer"] = reviewer
                waiting[reviewer.pk]["tours"] += 1

    sent = 0
    for item in waiting.values():
        reviewer = item["reviewer"]
        if _sent_today(reviewer, today):
            continue
        _notify(
            reviewer,
            reviewer,
            _message(item["leaves"], item["tours"]),
            "Requests waiting for your decision",
            route=APPROVALS_ROUTE if item["leaves"] else APPROVALS_TOURS_ROUTE,
            notification_type=settings.LEAVE_STATUS if item["leaves"] else settings.TOUR_STATUS,
        )
        sent += 1
    return sent
