"""
Finds working days an employee has not accounted for and reminds them before
the apply limit (CL_SL_WORKING_DAY_LIMIT / TOUR_LIMIT) runs out.

A gap is an Absent day, a working day with no attendance record, or a missing
punch-out. Half days are ignored. Days with a live leave or tour, Sundays,
holidays, closures and locked periods are never gaps.

Controlled by two AppSetting rows; without them the engine stays off:
- ATTENDANCE_GAP_ENGINE: "off", "report" (HR gets a report, employees nothing)
  or "live"
- ATTENDANCE_GAP_START: YYYY-MM-DD, days before this are never picked up

ATTENDANCE_GAP_EXCLUDE (optional) lists employee codes that are never scanned,
for people who don't punch: "KMPCL-000, KMPCL-012" or "000, 12".

A device that didn't sync would make everyone look absent, so a location with
no logs at all on a working day is skipped and reported to HR instead.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from hrms_app.hrms.utils import is_holiday, is_weekend
from hrms_app.models import (
    AppSetting,
    AttendanceGap,
    AttendanceLog,
    LeaveApplication,
    Notification,
    OfficeClosure,
    UserTour,
)
from hrms_app.services import attendance_lock
from hrms_app.services.mobile.attendance_codes import day_codes
from hrms_app.services.mobile.formatters import employee_code_label
from hrms_app.services.notification_push import ATTENDANCE_GAPS_ROUTE
from hrms_app.tasks import HR_EMAIL, send_leave_application_email

MODE_KEY = "ATTENDANCE_GAP_ENGINE"
START_KEY = "ATTENDANCE_GAP_START"
EXCLUDE_KEY = "ATTENDANCE_GAP_EXCLUDE"
LAST_RUN_KEY = "ATTENDANCE_GAP_LAST_RUN"
LIMIT_KEY = "CL_SL_WORKING_DAY_LIMIT"
DEFAULT_LIMIT = 4
LOOKBACK_DAYS = 7
ABSENT_CODES = {"A", "AWOL"}
LIVE_LEAVE_STATUSES = [
    settings.PENDING,
    settings.APPROVED,
    settings.RECOMMEND,
    settings.PENDING_CANCELLATION,
]
LIVE_TOUR_STATUSES = [
    settings.PENDING,
    settings.APPROVED,
    settings.EXTENDED,
    settings.PENDING_CANCELLATION,
    settings.COMPLETED,
]
KIND_LABELS = dict(AttendanceGap.KIND_CHOICES)


def _setting(key):
    row = AppSetting.objects.filter(key=key).first()
    return (row.value or "").strip() if row else ""


def engine_mode():
    mode = _setting(MODE_KEY).lower()
    return mode if mode in ("report", "live") else "off"


def _start_date():
    try:
        return date.fromisoformat(_setting(START_KEY))
    except ValueError:
        return None


def _is_working_day(day):
    return not (is_weekend(day) or is_holiday(day))


def last_apply_date(day):
    """Last working day a leave or tour ending on ``day`` can still be applied.

    Same count as the policy checks: ``day`` is working day 1, so a limit of 4
    leaves three more working days after it.
    """
    try:
        limit = int(_setting(LIMIT_KEY))
    except ValueError:
        limit = DEFAULT_LIMIT
    last, count, current = day, 1, day
    while True:
        current += timedelta(days=1)
        if not _is_working_day(current):
            continue
        count += 1
        if count > limit:
            return last
        last = current


def _covered_days(user, start, end):
    """Days with a live leave or tour. Pending counts: the employee has acted."""
    covered = set()
    leaves = LeaveApplication.objects.filter(
        appliedBy=user,
        status__in=LIVE_LEAVE_STATUSES,
        startDate__date__lte=end,
        endDate__date__gte=start,
    )
    for leave in leaves:
        covered |= _days(
            timezone.localtime(leave.startDate).date(), timezone.localtime(leave.endDate).date()
        )
    tours = UserTour.objects.filter(
        applied_by=user, status__in=LIVE_TOUR_STATUSES, start_date__lte=end
    ).filter(Q(end_date__gte=start) | Q(extended_end_date__gte=start))
    for tour in tours:
        covered |= _days(tour.start_date, tour.extended_end_date or tour.end_date)
    return covered


def _days(start, end):
    return {start + timedelta(days=n) for n in range((end - start).days + 1)}


def _unsynced_days(users, start, end):
    """{location id: days} for working days with no log at that location."""
    logged = defaultdict(set)
    logs = AttendanceLog.objects.filter(start_date__date__range=[start, end]).values_list(
        "applied_by__device_location_id", "start_date"
    )
    for location_id, moment in logs:
        logged[location_id].add(timezone.localtime(moment).date())

    working = {day for day in _days(start, end) if _is_working_day(day)}
    locations = {user.device_location_id for user in users}
    return {location_id: working - logged[location_id] for location_id in locations}


def detect_gaps(user, start, end, today, skip_days=frozenset()):
    """{day: kind} for one employee."""
    codes = day_codes(user, start, end, today=today)
    covered = _covered_days(user, start, end)
    logs = {
        timezone.localtime(log.start_date).date(): log
        for log in AttendanceLog.objects.filter(applied_by=user, start_date__date__range=[start, end])
    }
    joined = getattr(getattr(user, "personal_detail", None), "doj", None)

    gaps = {}
    for day in sorted(_days(start, end)):
        if day in skip_days or day in covered or (joined and day < joined):
            continue
        log = logs.get(day)
        if log and log.reg_status == settings.MIS_PUNCHING and not log.regularized:
            gaps[day] = AttendanceGap.MISSING_PUNCH
        elif codes.get(day, (None, None))[0] in ABSENT_CODES:
            gaps[day] = AttendanceGap.ABSENT if log else AttendanceGap.NO_RECORD
    return gaps


def _sync_rows(user, gaps, start, end):
    """Opens new gaps, closes the ones since resolved. A gap that comes back
    (say its leave was rejected) is announced again."""
    existing = {row.date: row for row in AttendanceGap.objects.filter(user=user, date__range=[start, end])}
    for day, kind in gaps.items():
        row = existing.get(day)
        if row is None:
            AttendanceGap.objects.create(user=user, date=day, kind=kind)
        elif not row.is_open or row.kind != kind:
            row.is_open, row.kind, row.first_notified_on = True, kind, None
            row.save(update_fields=["is_open", "kind", "first_notified_on", "updated_at"])
    for day, row in existing.items():
        if row.is_open and day not in gaps:
            row.is_open = False
            row.save(update_fields=["is_open", "updated_at"])


@dataclass
class GapGroup:
    """Neighbouring days of one kind. A single leave or tour can cover them
    all, so the deadline runs from the last day."""

    kind: str
    rows: list
    deadline: date

    @property
    def start(self):
        return self.rows[0].date

    @property
    def end(self):
        return self.rows[-1].date

    @property
    def dates_label(self):
        return _dates_label(self.start, self.end)

    @property
    def approval_mail(self):
        return next((r.approval_mail for r in self.rows if r.approval_mail_id), None)


def _dates_label(start, end):
    if start == end:
        return f"{start:%d %b %Y}"
    return f"{start:%d %b} to {end:%d %b %Y}"


def _family(kind):
    return "punch" if kind == AttendanceGap.MISSING_PUNCH else "absence"


def _group_rows(rows):
    groups, current = [], []
    for row in sorted(rows, key=lambda r: r.date):
        if current and _family(current[-1].kind) == _family(row.kind) and _neighbours(current[-1].date, row.date):
            current.append(row)
        else:
            if current:
                groups.append(current)
            current = [row]
    if current:
        groups.append(current)
    return [GapGroup(kind=g[0].kind, rows=g, deadline=last_apply_date(g[-1].date)) for g in groups]


def _neighbours(earlier, later):
    """Nothing but Sundays and holidays between the two days."""
    between = _days(earlier, later) - {earlier, later}
    return not any(_is_working_day(day) for day in between)


def open_groups(user):
    """What the employee still has to act on, without anything applied since
    the last scan. Empty until the engine is live."""
    if engine_mode() != "live":
        return []
    rows = list(AttendanceGap.objects.filter(user=user, is_open=True).select_related("approval_mail"))
    if not rows:
        return []
    covered = _covered_days(user, min(r.date for r in rows), max(r.date for r in rows))
    return _group_rows([r for r in rows if r.date not in covered])


def _message(group, stage):
    label = KIND_LABELS[group.kind]
    if group.kind == AttendanceGap.MISSING_PUNCH:
        if stage == "first":
            return f"Your punch-out is missing for {group.dates_label}. Please request approval."
        if stage == "last":
            return f"Today is the last day to request approval for the missing punch-out of {group.dates_label}."
        return f"The missing punch-out of {group.dates_label} is still open. Please request approval."
    if stage == "first":
        return f"{group.dates_label}: {label}. Apply leave or tour by {group.deadline:%d %b}."
    if stage == "last":
        return f"Today is the last day to apply CL, SL or tour for {group.dates_label}."
    return (
        f"The time to apply CL, SL or tour for {group.dates_label} has ended. "
        "Request approval from the app, or apply LWP."
    )


def _stage(group, today):
    """The reminder due today, if any: first / last / expired."""
    rows = group.rows
    if today > group.deadline:
        return "expired" if any(r.expired_notified_on is None for r in rows) else None
    if today == group.deadline:
        return "last" if any(r.last_day_notified_on is None for r in rows) else None
    return "first" if any(r.first_notified_on is None for r in rows) else None


_STAGE_FIELDS = {
    "first": ("first_notified_on",),
    "last": ("first_notified_on", "last_day_notified_on"),
    "expired": ("first_notified_on", "last_day_notified_on", "expired_notified_on"),
}


def _email_of(user):
    return user.official_email or user.email


def _notify(receiver, sender, text, subject):
    Notification.objects.create(
        sender=sender,
        receiver=receiver,
        message=text,
        notification_type=settings.ATTENDANCE_REGULARISATION,
        target_url="/",
        go_route_mobile=ATTENDANCE_GAPS_ROUTE,
    )
    email = _email_of(receiver)
    if email:
        body = f"Dear {receiver.first_name},\n\n{text}\n\nThank you,\nYour HR Team"
        transaction.on_commit(lambda: _queue_mail(subject, body, email))


def _queue_mail(subject, body, email):
    try:
        send_leave_application_email.delay(subject, body, [email])
    except Exception:
        pass  # the in-app notification and push still reach them


def send_reminders(user, today):
    """One message per employee per day, however many days are open."""
    due = []
    for group in _group_rows(
        list(AttendanceGap.objects.filter(user=user, is_open=True, approval_mail__isnull=True))
    ):
        stage = _stage(group, today)
        if stage:
            due.append((group, stage))
    if not due:
        return 0

    with transaction.atomic():
        lines = [_message(group, stage) for group, stage in due]
        _notify(user, user, "\n".join(lines), "Please update your attendance")
        manager = user.reports_to
        expired = [group for group, stage in due if stage == "expired"]
        if manager and expired:
            dates = ", ".join(group.dates_label for group in expired)
            name = user.get_full_name() or user.username
            _notify(
                manager,
                user,
                f"{name}'s attendance for {dates} was not updated in time.",
                "Attendance not updated",
            )
        for group, stage in due:
            for row in group.rows:
                for field in _STAGE_FIELDS[stage]:
                    if getattr(row, field) is None:
                        setattr(row, field, today)
                row.save(update_fields=[*_STAGE_FIELDS[stage], "updated_at"])
    return len(due)


def excluded_codes():
    """Employee codes never scanned, in one format whatever the admin typed."""
    return {employee_code_label(code) for code in _setting(EXCLUDE_KEY).split(",") if code.strip()}


def _scan_users():
    users = get_user_model().objects.filter(
        is_active=True, device_location__isnull=False, personal_detail__isnull=False
    ).select_related("personal_detail", "reports_to", "device_location")
    excluded = excluded_codes()
    return [
        user
        for user in users
        if not {
            employee_code_label(user.username),
            employee_code_label(user.personal_detail.employee_code),
        }
        & excluded
    ]


def _report_to_hr(today, found, unsynced, mode):
    lines = [f"Attendance gap scan for {today:%d %b %Y} ({mode} mode)."]
    if unsynced:
        lines += ["", "No device data, so these days were skipped:"]
        lines += [f"- {name}: {', '.join(f'{d:%d %b}' for d in sorted(days))}" for name, days in unsynced.items()]
    lines += ["", f"Employees with open gaps: {len(found)}"]
    for name, gaps in found.items():
        days = ", ".join(f"{day:%d %b} ({KIND_LABELS[kind]})" for day, kind in sorted(gaps.items()))
        lines.append(f"- {name}: {days}")
    _queue_mail("Attendance gap report", "\n".join(lines), HR_EMAIL)


def scan(today=None):
    """The daily job. Safe to run twice: rows are unique per employee and date,
    and it looks back a week, so a missed run heals itself."""
    today = today or timezone.localdate()
    mode, go_live = engine_mode(), _start_date()
    if mode == "off" or go_live is None:
        return {"mode": mode, "employees": 0}

    # Older open days stay in the window, so one regularized later still closes.
    oldest_open = AttendanceGap.objects.filter(is_open=True).order_by("date").first()
    start = today - timedelta(days=LOOKBACK_DAYS)
    if oldest_open and oldest_open.date < start:
        start = oldest_open.date
    start, end = max(go_live, start), today - timedelta(days=1)
    if start > end:
        return {"mode": mode, "employees": 0}

    users = _scan_users()
    unsynced = _unsynced_days(users, start, end)
    closed = set(OfficeClosure.objects.filter(date__range=[start, end]).values_list("date", flat=True))
    locked = {day for day in _days(start, end) if attendance_lock.active_lock(day)}

    found, reminders = {}, 0
    for user in users:
        skip = closed | locked | unsynced.get(user.device_location_id, set())
        gaps = detect_gaps(user, start, end, today, skip)
        _sync_rows(user, gaps, start, end)
        if gaps:
            found[user.get_full_name() or user.username] = gaps
        if mode == "live":
            reminders += send_reminders(user, today)

    missing_sync = {
        str(next(u.device_location for u in users if u.device_location_id == location_id)): days
        for location_id, days in unsynced.items()
        if days
    }
    if mode == "report" or missing_sync:
        _report_to_hr(today, found, missing_sync, mode)
    _mark_run(today)
    return {"mode": mode, "employees": len(found), "reminders": reminders}


def _mark_run(today):
    AppSetting.objects.update_or_create(
        key=LAST_RUN_KEY, defaults={"value": today.isoformat(), "beyond_policy": False}
    )


def alert_admins(text):
    """Tells the superusers in the app and HR by mail that the engine needs a look."""
    superusers = list(get_user_model().objects.filter(is_active=True, is_superuser=True))
    for admin in superusers:
        Notification.objects.create(
            sender=admin,
            receiver=admin,
            message=text,
            notification_type=settings.ATTENDANCE_REGULARISATION,
            target_url="/",
        )
    _queue_mail("Attendance reminder engine alert", text, HR_EMAIL)


def check_health(today=None):
    """Later in the morning: did today's scan run? Returns True when fine."""
    today = today or timezone.localdate()
    if engine_mode() == "off" or _start_date() is None or _setting(LAST_RUN_KEY) == today.isoformat():
        return True
    alert_admins(f"The attendance reminder scan did not run on {today:%d %b %Y}. Please check the server.")
    return False
