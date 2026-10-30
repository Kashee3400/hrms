"""
Who can see and decide tour applications in the mobile app.

Same reviewers as leave (services/leave_approval.py). The queue is wider than
the web tracker's: a cancellation request needs the manager's decision too.
"""
from django.conf import settings

from hrms_app.models import UserTour
from hrms_app.services.leave_approval import is_admin_department

AWAITING = [settings.PENDING, settings.EXTENDED, settings.PENDING_CANCELLATION]


def review_queue(user):
    """Tours waiting for this user's decision."""
    queue = UserTour.objects.filter(status__in=AWAITING).exclude(applied_by=user)
    return queue if user.is_superuser else queue.filter(applied_by__in=user.employees.all())


def reviewable(user):
    """Every tour this user may open as a reviewer (any status)."""
    if user.is_superuser or user.is_staff or is_admin_department(user):
        return UserTour.objects.exclude(applied_by=user)
    return UserTour.objects.filter(applied_by__in=user.employees.all())
