"""
Final status code per day (P, H, A, CL, CLH, T, OFF, holiday codes…) from
the same AttendanceMapper the web uses, plus helpers to group and label
them. Shared by the Home month summary and the Attendance calendar.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Q

from hrms_app.models import Holiday, LeaveType
from hrms_app.utility.attendance_mapper import aggregate_attendance_data

OFF_COLOR = "#CCCCCC"
ABSENT_COLOR = "#FF0000"
TOUR_COLOR = "#06c1c4"

# Fixed codes produced by the mapper / attendance logs.
FIXED_LABELS = {
    "P": "Present",
    "H": "Half Day",
    "A": "Absent",
    "AWOL": "Absent (AWOL)",
    "OFF": "Weekly Off",
    "T": "Tour",
    "TH": "Tour (Half Day)",
    "FL": "Holiday",
}

CATEGORIES = ("present", "half_day", "absent", "leave", "tour", "holiday", "off")


@dataclass(frozen=True)
class LeaveCodes:
    """Leave short codes (full + half-day) -> (label, colour)."""

    labels: dict

    @classmethod
    def load(cls):
        labels = {}
        for lt in LeaveType.objects.all():
            if lt.leave_type_short_code:
                labels[lt.leave_type_short_code] = (lt.leave_type, lt.color_hex)
            if lt.half_day_short_code:
                labels[lt.half_day_short_code] = (f"{lt.leave_type} (Half Day)", lt.color_hex)
        return cls(labels)

    def __contains__(self, code):
        return code in self.labels


def classify(code, leave_codes):
    """Summary bucket for a final day code."""
    if code == "P":
        return "present"
    if code == "H":
        return "half_day"
    if code in ("A", "AWOL"):
        return "absent"
    if code in ("T", "TH"):
        return "tour"
    if code == "OFF":
        return "off"
    if code in leave_codes:
        return "leave"
    return "holiday"


def applicable_holidays(user, start, end):
    """Holidays overlapping the range that apply to this user (blank = everyone)."""
    return (
        Holiday.objects.filter(start_date__lte=end, end_date__gte=start)
        .filter(Q(applicable_users__isnull=True) | Q(applicable_users=user))
        .distinct()
    )


def day_codes(user, start, end, *, today):
    """{date: (code, colour)} for every day in [start, end].

    The mapper result wins. Days it left empty get the obvious fallback
    (it only applies Sundays/holidays to employees that already have data):
    Sunday -> OFF, holiday -> its code, past day -> A, today/future -> None.
    """
    mapped = aggregate_attendance_data([user.pk], start, end).get(user.pk, {})

    holiday_days = {}
    for holiday in applicable_holidays(user, start, end):
        current = holiday.start_date
        while current <= (holiday.end_date or holiday.start_date):
            holiday_days[current] = (holiday.short_code or "FL", holiday.color_hex)
            current += timedelta(days=1)

    result = {}
    current = start
    while current <= end:
        entries = mapped.get(current) or []
        if entries and entries[0].get("status"):
            result[current] = (entries[0]["status"], entries[0].get("color"))
        elif current in holiday_days:
            result[current] = holiday_days[current]
        elif current.weekday() == 6:
            result[current] = ("OFF", OFF_COLOR)
        elif current < today:
            result[current] = ("A", ABSENT_COLOR)
        else:
            result[current] = (None, None)
        current += timedelta(days=1)
    return result


def summarize(codes, leave_codes, until):
    """Category counts for the days in `codes` up to and including `until`."""
    counts = dict.fromkeys(CATEGORIES, 0)
    for day, (code, _) in codes.items():
        if code and day <= until:
            counts[classify(code, leave_codes)] += 1
    return counts


def flag_counts(user, start, end):
    """Late coming / early going / missing punch-out days from attendance logs."""
    from django.conf import settings

    from hrms_app.models import AttendanceLog

    logs = AttendanceLog.objects.filter(applied_by=user, start_date__date__range=[start, end])
    return {
        "late_coming": logs.filter(reg_status=settings.LATE_COMING).count(),
        "early_going": logs.filter(reg_status=settings.EARLY_GOING).count(),
        "missing_punch": logs.filter(reg_status=settings.MIS_PUNCHING).count(),
    }
