"""
The employee's own tours for the mobile Tours tab.

Validation is the web's TourForm. Actions mirror the web detail page:
- pending            -> Edit, Delete
- approved, extended -> Cancel request (status -> pending_cancellation; the
                        manager then cancels)
Mobile only:
- approved, rejected -> Re-request with a new start time / end date & time
                        (status -> pending; the manager decides again)
"""
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from hrms_app.forms.tour_form import TourDateTimeUpdateForm
from hrms_app.hrms.form import TourForm
from hrms_app.models import TourDateTimeChangeLog, TourStatusLog, UserTour
from hrms_app.services import attendance_lock
from hrms_app.services.mobile.formatters import hhmm, iso_date, plain_text
from hrms_app.services.mobile.home_summary import active_tour, tour_payload
from hrms_app.services.mobile.my_leaves import PAGE_SIZE, _person
from hrms_app.services.workflow_messages import tour_label
from hrms_app.tasks import send_tour_notifications

ADD_PERMISSION = "hrms_app.add_usertour"
CHANGE_PERMISSION = "hrms_app.change_usertour"
DELETE_PERMISSION = "hrms_app.delete_usertour"
EDITABLE = {settings.PENDING}
CANCELLABLE = {settings.APPROVED, settings.EXTENDED}
REREQUESTABLE = {settings.APPROVED, settings.REJECTED}

# Status filter values the app sends -> statuses they cover.
STATUS_GROUPS = {
    "pending": [settings.PENDING, settings.EXTENDED],
    "approved": [settings.APPROVED, settings.COMPLETED],
    "rejected": [settings.REJECTED],
    "cancelled": [settings.CANCELLED, settings.PENDING_CANCELLATION],
}

_REQUIRED = {
    "approval_type": "Select the approval type.",
    "from_destination": "Enter the boarding location.",
    "to_destination": "Enter the destination.",
    "start_date": "Select the start date.",
    "start_time": "Select the start time.",
    "end_date": "Select the end date.",
    "end_time": "Select the end time.",
    "remarks": "Enter the remark & objectives.",
}


def tour_lock(tour):
    """Lock info for the tour's whole date range (audit freeze)."""
    return attendance_lock.lock_info(tour.start_date, tour.extended_end_date or tour.end_date)


def _actions(user, tour, lock):
    open_ = tour.applied_by_id == user.pk and not lock["is_locked"]
    return {
        "can_cancel": open_ and tour.status in CANCELLABLE and user.has_perm(CHANGE_PERMISSION),
        "can_edit": open_ and tour.status in EDITABLE and user.has_perm(CHANGE_PERMISSION),
        "can_delete": open_ and tour.status in EDITABLE and user.has_perm(DELETE_PERMISSION),
        "can_rerequest": open_ and tour.status in REREQUESTABLE and user.has_perm(CHANGE_PERMISSION),
    }


def tour_item(user, tour):
    lock = tour_lock(tour)
    return {
        **tour_payload(tour),
        "duration": tour.formatted_duration,
        "applied_on": timezone.localtime(tour.created_at).isoformat(),
        **lock,
        **_actions(user, tour, lock),
    }


def _log_note(comments):
    """The model logs "Approved by x. Reason: y"; the app shows only y."""
    note = plain_text(comments).rsplit("Reason:", 1)[-1].strip()
    return "" if note == "None" else note


def _last_change(tour):
    """The schedule before the latest re-request, for the manager to compare."""
    change = tour.datetime_change_logs.first() if tour.status == settings.PENDING else None
    if change is None:
        return None
    return {
        "start_time": hhmm(change.previous_start_time),
        "end_date": iso_date(change.previous_end_date),
        "end_time": hhmm(change.previous_end_time),
        "reason": change.reason or "",
    }


def tour_detail(user, tour, build_url):
    return {
        **tour_item(user, tour),
        "last_change": _last_change(tour),
        "approver": _person(tour.applied_by.reports_to),
        "pdf_url": build_url(reverse("generate_tour_pdf", kwargs={"slug": tour.slug})),
        "logs": [
            {
                "action": log.action or "",
                "by": log.action_by_name or "",
                "at": timezone.localtime(log.timestamp).isoformat(),
                "notes": _log_note(log.comments),
            }
            for log in tour.logs.order_by("timestamp")
        ],
    }


def get_apply_options(user):
    """Everything the form needs before the first keystroke."""
    return {
        "can_apply": user.has_perm(ADD_PERMISSION),
        "approver": _person(user.reports_to),
        "approval_types": [
            {"value": value, "label": str(label)} for value, label in settings.APPROVAL_TYPE_CHOICES
        ],
    }


def get_overview(user, year):
    counts = UserTour.objects.filter(applied_by=user, start_date__year=year).aggregate(
        total=Count("pk"),
        **{
            group: Count("pk", filter=Q(status__in=statuses))
            for group, statuses in STATUS_GROUPS.items()
        },
    )
    return {"year": year, "counts": counts, "active_tour": active_tour(user, timezone.localdate())}


def list_tours(user, *, year, status, page):
    queryset = UserTour.objects.filter(applied_by=user, start_date__year=year)
    if status in STATUS_GROUPS:
        queryset = queryset.filter(status__in=STATUS_GROUPS[status])
    queryset = queryset.order_by("-start_date", "-pk")

    total = queryset.count()
    start = (max(page, 1) - 1) * PAGE_SIZE
    return {
        "results": [tour_item(user, tour) for tour in queryset[start : start + PAGE_SIZE]],
        "page": max(page, 1),
        "total": total,
        "has_next": start + PAGE_SIZE < total,
    }


def get_own_tour(user, tour_id):
    return (
        UserTour.objects.filter(applied_by=user, pk=tour_id)
        .select_related("applied_by__reports_to__personal_detail__designation__department")
        .first()
    )


def _parse_input(data):
    """Field values for TourForm, or errors. Its clean() needs real dates."""
    fields = {name: str(data.get(name) or "").strip() for name in _REQUIRED}
    errors = {name: [message] for name, message in _REQUIRED.items() if not fields[name]}
    for name, parse in (
        ("start_date", parse_date),
        ("end_date", parse_date),
        ("start_time", parse_time),
        ("end_time", parse_time),
    ):
        if name in errors:
            continue
        try:
            valid = parse(fields[name]) is not None
        except ValueError:
            valid = False
        if not valid:
            errors[name] = [_REQUIRED[name]]
    return fields, errors


def save_tour(user, data, instance=None):
    """Creates or edits a tour. Returns (tour, errors)."""
    fields, errors = _parse_input(data)
    if errors:
        return None, errors
    lock = attendance_lock.active_lock(parse_date(fields["start_date"]), parse_date(fields["end_date"]))
    if lock:
        return None, {"__all__": [attendance_lock.lock_message(lock)]}

    form = TourForm(fields, user=user, instance=instance)
    try:
        valid = form.is_valid()
    except AttributeError:  # the form's leave-conflict check needs a shift
        return None, {"__all__": ["Shift details not found. Please contact HR."]}
    if not valid:
        return None, {name: [str(error) for error in messages] for name, messages in form.errors.items()}

    tour = form.save(commit=False)
    if instance is None:
        tour.applied_by = user
    try:
        with transaction.atomic():
            tour.save()
            if instance is not None:
                TourStatusLog.create_log(tour=tour, action_by=user, action="Updated")
    except PermissionDenied as exc:  # the web's pre_save lock guard
        return None, {"__all__": [str(exc)]}
    _send_emails(tour, edited=instance is not None)
    return tour, None


def policy_block(user, data):
    """The TOUR_LIMIT refusal for this tour, or None if that's not what stops it."""
    fields, errors = _parse_input(data)
    if errors:
        return None
    form = TourForm(fields, user=user)
    try:
        form.is_valid()
    except AttributeError:
        return None
    return next((m for m in form.non_field_errors() if "denied" in m), None)


def _send_emails(tour, *, edited):
    """Like the web's apply/edit views; a queue outage must not fail the request."""
    texts = {}
    if edited:
        label = tour_label(tour)
        name = tour.applied_by.get_full_name() or tour.applied_by.username
        texts = {
            "employee_text": f"Your {label} has been updated.",
            "manager_text": f"{name} updated {label}. Please review it.",
        }
    try:
        send_tour_notifications.delay(tour.id, "http", Site.objects.get_current().domain, **texts)
    except Exception:
        pass


def request_cancellation(user, tour, reason):
    """Returns None on success or a message saying why it was refused."""
    reason = (reason or "").strip()
    if not reason:
        return "Please give a reason for the cancellation."
    if not tour_item(user, tour)["can_cancel"]:
        return tour_lock(tour)["lock_reason"] or "This tour can't be cancelled."
    try:
        tour.pending_cancel(action_by=user, reason=reason)
    except PermissionDenied as exc:
        return str(exc)
    return None


def rerequest_tour(user, tour, data):
    """Changes the start time / end date & time and sends the tour back to the
    manager as pending. Returns (tour, errors).

    Pre/Post-approval timing is not re-checked: a tour already under way must
    still be able to correct its times, and the manager decides again.
    """
    if not tour_item(user, tour)["can_rerequest"]:
        return None, {"__all__": [tour_lock(tour)["lock_reason"] or "This tour can't be updated."]}

    previous = {name: getattr(tour, name) for name in ("start_date", "start_time", "end_date", "end_time")}
    form = TourDateTimeUpdateForm(
        {
            "start_date": tour.start_date.isoformat(),
            "start_time": str(data.get("start_time") or "").strip(),
            "end_date": str(data.get("end_date") or "").strip(),
            "end_time": str(data.get("end_time") or "").strip(),
            "reason": str(data.get("reason") or "").strip(),
        },
        instance=tour,
    )
    if not form.is_valid():
        return None, {name: [str(error) for error in messages] for name, messages in form.errors.items()}

    start_date, start_time = form.cleaned_data["start_date"], form.cleaned_data["start_time"]
    end_date, end_time = form.cleaned_data["end_date"], form.cleaned_data["end_time"]
    if start_date == end_date and start_time >= end_time:
        return None, {"__all__": ["End time must be after start time on the same day."]}
    if (start_time, end_date, end_time) == (previous["start_time"], previous["end_date"], previous["end_time"]):
        return None, {"__all__": ["Change the start time or the end date & time first."]}

    lock = attendance_lock.active_lock(start_date, max(end_date, previous["end_date"]))
    if lock:
        return None, {"__all__": [attendance_lock.lock_message(lock)]}

    # The same conflict and time-limit checks as applying (TourForm.clean).
    rules = TourForm(user=user, instance=tour)
    try:
        rules._validate_attendance_conflict(start_date, end_time, start_time)
        rules._validate_leave_conflict(start_date, end_date, start_time, end_time)
        rules._apply_tour_policy(end_date, user)
    except ValidationError as exc:
        return None, {"__all__": exc.messages}
    except AttributeError:  # the leave-conflict check needs a shift
        return None, {"__all__": ["Shift details not found. Please contact HR."]}

    reason = form.cleaned_data["reason"]
    tour = form.save(commit=False)
    tour.status = settings.PENDING
    tour.extended_end_date = tour.extended_end_time = None
    tour._rerequested = True  # the signal then notifies the manager
    try:
        with transaction.atomic():
            tour.save()
            TourDateTimeChangeLog.create_from_diff(tour, previous, user, reason=reason)
            TourStatusLog.create_log(tour=tour, action_by=user, action="Re-requested", comments=reason)
    except PermissionDenied as exc:  # the web's pre_save lock guard
        return None, {"__all__": [str(exc)]}
    return tour, None  # the status change emails both


def delete_tour(user, tour):
    """Returns None on success or a message saying why it was refused."""
    if not tour_item(user, tour)["can_delete"]:
        return tour_lock(tour)["lock_reason"] or "Only a pending tour can be deleted."
    try:
        tour.delete()
    except PermissionDenied as exc:
        return str(exc)
    return None
