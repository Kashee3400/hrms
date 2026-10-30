"""Small JSON helpers shared by the mobile API payload builders."""


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
