"""Small JSON helpers shared by the mobile API payload builders."""
import html
from datetime import datetime

from django.utils.html import strip_tags

# One word for each decision: the web's forms also log "Approve", "Extended".
_ACTION_WORDS = {
    "approve": "approved",
    "reject": "rejected",
    "cancel": "cancelled",
    "extend": "extended",
    "extended": "extended",
}
SAME_EVENT_SECONDS = 60


def plain_text(text):
    """CKEditor HTML -> plain text for the app."""
    return html.unescape(strip_tags(text or "")).strip()


def timeline(entries):
    """Log rows for the app: newest first, one row per event.

    ``entries`` are oldest first. A single web save can log one decision twice,
    so the same action by the same person within a minute is shown once. The
    stored logs stay as they are.
    """
    merged = []
    for entry in entries:
        action = _ACTION_WORDS.get(entry["action"].lower(), entry["action"])
        last = merged[-1] if merged else None
        if (
            last
            and last["by"] == entry["by"]
            and last["action"].lower() == action.lower()
            and (datetime.fromisoformat(entry["at"]) - datetime.fromisoformat(last["at"])).total_seconds()
            < SAME_EVENT_SECONDS
        ):
            last["notes"] = last["notes"] or entry["notes"]
            continue
        merged.append({**entry, "action": action})
    return merged[::-1]


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
