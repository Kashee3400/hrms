"""Small JSON helpers shared by the mobile API payload builders."""
import html

from django.utils.html import strip_tags


def plain_text(text):
    """CKEditor HTML -> plain text for the app."""
    return html.unescape(strip_tags(text or "")).strip()


def employee_code_label(code):
    """Company format, always three digits: "7" -> "KMPCL-007", "033" -> "KMPCL-033"."""
    text = str(code or "").strip()
    number = text.upper().removeprefix("KMPCL-")
    return f"KMPCL-{number.zfill(3)}" if number.isdigit() else (text or None)


def iso_date(value):
    return value.isoformat() if value else None


def hhmm(value):
    """time -> "HH:MM" (24h); the app formats it for display."""
    return value.strftime("%H:%M") if value else None


def shift_payload(user):
    """The employee's current shift (last assigned), or None."""
    employee_shift = user.shifts.select_related("shift_timing").last()
    if not employee_shift:
        return None
    shift = employee_shift.shift_timing
    return {
        "start_time": hhmm(shift.start_time),
        "end_time": hhmm(shift.end_time),
        "grace_till": hhmm(shift.grace_start_time),
        "break_minutes": shift.break_duration,
    }
