"""
Application Settings for superusers in the mobile app (the same AppSetting rows
as the web admin). The settings the code reads are described here, so the app
can show the right input and a wrong value is refused. They appear even before
their row exists; the first save creates it. Any other row is plain text.
"""
from datetime import date

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from hrms_app.models import AppSetting, LeaveType
from hrms_app.services.attendance_gaps import EXCLUDE_KEY, LIMIT_KEY, MODE_KEY, START_KEY
from hrms_app.services.mobile.formatters import employee_code_label

NUMBER, CHOICE, DATE, TEXT = "number", "choice", "date", "text"
LIMITS, REMINDERS, OTHER = "Apply Limits", "Attendance Reminders", "Other"

# key -> (title, help, type, group, uses beyond_policy / allowed_users)
SETTINGS = {
    LIMIT_KEY: (
        "CL / SL Apply Limit",
        "Working days counted from the leave's last day. 4 means 3 days after it.",
        NUMBER,
        LIMITS,
        True,
    ),
    "TOUR_LIMIT": (
        "Tour Apply Limit",
        "Working days counted from the tour's last day. 4 means 3 days after it.",
        NUMBER,
        LIMITS,
        True,
    ),
    "REGULARIZATION_LIMIT": ("Regularization Limit", "Requests allowed in a month.", NUMBER, LIMITS, True),
    "REGULARIZATION_MAX_HR": ("Regularization Max Hours", "Longest time one request can cover.", NUMBER, LIMITS, True),
    MODE_KEY: (
        "Reminder Engine",
        "Off: nothing runs. Report: only HR gets the daily report. Live: employees get reminders.",
        CHOICE,
        REMINDERS,
        False,
    ),
    START_KEY: ("Reminders Start From", "Days before this date are never picked up.", DATE, REMINDERS, False),
    EXCLUDE_KEY: (
        "Excluded Employees",
        "Employee codes that get no reminders, separated by commas. Example: KMPCL-000, KMPCL-012",
        TEXT,
        REMINDERS,
        False,
    ),
}
CHOICES = {MODE_KEY: ["off", "report", "live"]}


def _employee(user):
    return {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        "code": employee_code_label(user.username),
    }


def _payload(key, row):
    title, help_text, kind, group, has_policy = SETTINGS.get(key, (key, "", TEXT, OTHER, True))
    return {
        "key": key,
        "title": title,
        "help": (row.description if row and not help_text else help_text) or "",
        "type": kind,
        "group": group,
        "choices": CHOICES.get(key, []),
        "value": row.value if row else "",
        "has_policy": has_policy,
        "beyond_policy": row.beyond_policy if row else False,
        "allowed_users": [_employee(user) for user in row.allowed_users.all()] if row and has_policy else [],
        "updated_at": row.updated_at.isoformat() if row else None,
    }


def get_settings():
    rows = {row.key: row for row in AppSetting.objects.prefetch_related("allowed_users")}
    keys = [*SETTINGS, *sorted(key for key in rows if key not in SETTINGS)]
    users = get_user_model().objects.filter(is_active=True).order_by("first_name", "last_name")
    return {
        "settings": [_payload(key, rows.get(key)) for key in keys],
        "employees": [_employee(user) for user in users],
        "el_policy": get_el_policy(),
    }


def _clean_value(key, value):
    """Returns (value, error)."""
    value = str(value if value is not None else "").strip()
    kind = SETTINGS.get(key, (None, None, TEXT))[2]
    if kind == NUMBER and not value.isdigit():
        return None, "Enter a whole number."
    if kind == CHOICE and value not in CHOICES[key]:
        return None, "Select a valid option."
    if kind == DATE:
        try:
            date.fromisoformat(value)
        except ValueError:
            return None, "Select a valid date."
    if len(value) > 255:
        return None, "Keep this under 255 characters."
    if key == MODE_KEY and value != "off" and not _has_start_date():
        return None, "Set 'Reminders Start From' first."
    return value, None


def _has_start_date():
    return AppSetting.objects.filter(key=START_KEY).exclude(value="").exists()


def _log(actor, row, old_value, created):
    """Shows in the setting's History on the web admin."""
    LogEntry.objects.create(
        user_id=actor.pk,
        content_type_id=ContentType.objects.get_for_model(AppSetting).pk,
        object_id=str(row.pk),
        object_repr=str(row)[:200],
        action_flag=CHANGE,
        change_message=(
            f"Created from the mobile app: {row.value}"
            if created
            else f"Changed from the mobile app: {old_value} -> {row.value}, "
            f"beyond policy {row.beyond_policy}"
        ),
        action_time=timezone.now(),
    )


def update_setting(actor, key, data):
    """Returns (payload, error message)."""
    row = AppSetting.objects.filter(key=key).first()
    if row is None and key not in SETTINGS:
        return None, "Setting not found."
    value, error = _clean_value(key, data.get("value"))
    if error:
        return None, error

    has_policy = SETTINGS.get(key, (0, 0, 0, 0, True))[4]
    with transaction.atomic():
        created = row is None
        old_value = row.value if row else ""
        if created:
            # The model defaults this on, which would switch the limit off.
            row = AppSetting(key=key, beyond_policy=False)
        row.value = value
        if has_policy:
            row.beyond_policy = bool(data.get("beyond_policy"))
        row.save()
        if has_policy:
            row.allowed_users.set(
                get_user_model().objects.filter(pk__in=data.get("allowed_users") or [], is_active=True)
            )
        _log(actor, row, old_value, created)
    return _payload(key, row), None


# ─────────────────────────────────────────────────────────────
# EL policy (fields of the EL LeaveType row)
# ─────────────────────────────────────────────────────────────

EL_CODE = "EL"


def _el_type():
    return LeaveType.objects.filter(leave_type_short_code=EL_CODE).first()


def _el_policy(el):
    return {
        "allow_half_day": el.allow_half_day,
        "half_day_value": el.half_day_value,
        "min_days_limit": el.min_days_limit,
        "min_notice_days": el.min_notice_days,
        "restricted_after": list(el.restricted_after_leave_types.values_list("pk", flat=True)),
        # EL's list says what can't follow EL. What stops EL itself is on these.
        "blocked_by": list(
            LeaveType.objects.filter(restricted_after_leave_types=el).values_list(
                "leave_type_short_code", flat=True
            )
        ),
        "leave_types": [
            {"id": item.pk, "code": item.leave_type_short_code}
            for item in LeaveType.objects.order_by("leave_type_short_code")
        ],
    }


def get_el_policy():
    el = _el_type()
    return _el_policy(el) if el else None


def _number(data, name, label, *, required=False):
    """Returns (value or None, error). Blank switches an optional rule off."""
    raw = data.get(name)
    if raw in (None, ""):
        return None, f"Enter {label}." if required else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f"Enter a valid number for {label}."
    return (None, f"{label} can't be negative.") if value < 0 else (value, None)


def update_el_policy(actor, data):
    """Returns (payload, error message). Applies to new applications at once."""
    el = _el_type()
    if el is None:
        return None, "EL leave type not found."
    half_value, error = _number(data, "half_day_value", "half day value", required=True)
    if not error and not 0 < half_value <= 1:
        error = "Half day value must be between 0 and 1."
    min_days, days_error = _number(data, "min_days_limit", "min days limit")
    notice, notice_error = _number(data, "min_notice_days", "min notice days")
    error = error or days_error or notice_error
    if error:
        return None, error

    before = _el_policy(el)
    with transaction.atomic():
        el.allow_half_day = bool(data.get("allow_half_day"))
        el.half_day_value = half_value
        el.min_days_limit = min_days
        el.min_notice_days = notice
        el.save()
        el.restricted_after_leave_types.set(
            LeaveType.objects.filter(pk__in=data.get("restricted_after") or [])
        )
        after = _el_policy(el)
        changes = {key: (before[key], after[key]) for key in after if before[key] != after[key]}
        LogEntry.objects.create(
            user_id=actor.pk,
            content_type_id=ContentType.objects.get_for_model(LeaveType).pk,
            object_id=str(el.pk),
            object_repr=str(el)[:200],
            action_flag=CHANGE,
            change_message=f"EL policy changed from the mobile app: {changes}",
            action_time=timezone.now(),
        )
    return after, None
