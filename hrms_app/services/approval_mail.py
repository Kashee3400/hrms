"""
Writes the beyond-policy approval mail for the employee. They read it, confirm
and it goes to their manager with themselves and HR in copy; the manager then
forwards it to the competent authority. The decision stays on email.

The server builds the mail from its own data on both preview and send, so what
the employee saw is exactly what goes out.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone

from hrms_app.models import ApprovalMail, AttendanceGap
from hrms_app.services.attendance_gaps import KIND_LABELS, open_groups
from hrms_app.services.mobile import leave_apply, tours
from hrms_app.services.mobile.formatters import employee_code_label
from hrms_app.tasks import HR_EMAIL, send_approval_mail

MAX_REASON = 1000


def _attendance_request(user, data):
    start, end = _dates(data)
    groups = [g for g in open_groups(user) if g.start <= end and g.end >= start]
    if not groups:
        return None, "This attendance is already up to date."
    group = groups[0]
    label = KIND_LABELS[group.kind]
    return {
        "start": group.start,
        "end": group.end,
        "title": f"{label} on {group.dates_label}",
        "note": (
            "The punch-out was not recorded on this day."
            if group.kind == AttendanceGap.MISSING_PUNCH
            else "The time limit to apply for this day has passed."
        ),
        "group": group,
    }, None


def _leave_request(user, data):
    leave_input, errors = leave_apply.parse_input(user, data)
    if errors:
        return None, next(iter(errors.values()))
    summary = leave_apply.preview(user, leave_input)
    if not summary["approval_needed"]:
        return None, "This leave doesn't need an approval mail."
    name = leave_input.leave_type.leave_type
    return {
        "start": leave_input.start,
        "end": leave_input.end,
        "title": f"{name} from {leave_input.start:%d %b %Y} to {leave_input.end:%d %b %Y}",
        "note": " ".join(summary["errors"]),
    }, None


def _tour_request(user, data):
    note = tours.policy_block(user, data)
    if note is None:
        return None, "This tour doesn't need an approval mail."
    start, end = _dates(data)
    return {
        "start": start,
        "end": end,
        "title": (
            f"Tour {data.get('from_destination')} to {data.get('to_destination')}, "
            f"{start:%d %b %Y} to {end:%d %b %Y}"
        ),
        "note": note,
    }, None


def _dates(data):
    start = date.fromisoformat(str(data.get("start_date")))
    return start, date.fromisoformat(str(data.get("end_date") or start))


_REQUESTS = {
    ApprovalMail.ATTENDANCE: _attendance_request,
    ApprovalMail.LEAVE_POLICY: _leave_request,
    ApprovalMail.TOUR_POLICY: _tour_request,
}


def _recipients(user):
    employee = user.official_email or user.email
    manager = user.reports_to
    manager_email = (manager.official_email or manager.email) if manager else None
    to = manager_email or HR_EMAIL
    cc = [email for email in (employee, HR_EMAIL) if email and email != to]
    return to, list(dict.fromkeys(cc)), manager


def _compose(user, request, reason):
    to, cc, manager = _recipients(user)
    details = getattr(user, "personal_detail", None)
    designation = getattr(details, "designation", None)
    name = user.get_full_name() or user.username
    code = employee_code_label(getattr(details, "employee_code", None) or user.username)
    greeting = (manager.get_full_name() or manager.username) if manager else "HR Team"
    lines = [
        f"Dear {greeting},",
        "",
        "Please forward this request to the competent authority for approval.",
        "",
        f"Employee: {name} ({code})",
    ]
    if designation:
        lines.append(f"Designation: {designation}")
    lines += [
        f"Request: {request['title']}",
        f"Policy note: {request['note']}",
        f"Reason: {reason}",
        "",
        "Regards,",
        name,
    ]
    return {
        "subject": f"Approval request: {request['title']} - {name}",
        "body": "\n".join(lines),
        "to": to,
        "cc": cc,
    }


def _prepare(user, data):
    """(request, mail, error message)."""
    kind = data.get("kind")
    build = _REQUESTS.get(kind)
    if build is None:
        return None, None, "Unknown request."
    reason = str(data.get("reason") or "").strip()
    if not reason:
        return None, None, "Please give a reason."
    if len(reason) > MAX_REASON:
        return None, None, f"Keep the reason under {MAX_REASON} characters."
    try:
        request, error = build(user, data)
    except ValueError:
        return None, None, "Enter valid dates."
    if error:
        return None, None, error[0] if isinstance(error, list) else error

    sent = ApprovalMail.objects.filter(
        user=user, kind=kind, start_date=request["start"], end_date=request["end"]
    ).first()
    if sent:
        when = timezone.localtime(sent.sent_at)
        return None, None, f"You already sent this approval mail on {when:%d %b %Y}."
    return request, _compose(user, request, reason), None


def preview(user, data):
    """Returns (mail, error message)."""
    _, mail, error = _prepare(user, data)
    return mail, error


def send(user, data):
    """Sends the mail and records it. Returns an error message or None."""
    request, mail, error = _prepare(user, data)
    if error:
        return error
    with transaction.atomic():
        record = ApprovalMail.objects.create(
            user=user,
            kind=data["kind"],
            start_date=request["start"],
            end_date=request["end"],
            subject=mail["subject"],
            body=mail["body"],
            reason=str(data["reason"]).strip(),
            to_email=mail["to"],
            cc_emails=mail["cc"],
        )
        group = request.get("group")
        if group:
            AttendanceGap.objects.filter(pk__in=[row.pk for row in group.rows]).update(approval_mail=record)
        reply_to = user.official_email or user.email
        transaction.on_commit(
            lambda: send_approval_mail.delay(mail["subject"], mail["body"], mail["to"], mail["cc"], reply_to)
        )
    return None
