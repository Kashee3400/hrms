"""
A reporting manager's view of their direct reportees: the month grid of the
web's "Monthly Attendance Overview" and today's headcount.

Everyone, the CEO included, sees only their own reportees. Attendance logs are
written at night, so today's punches are read live from the biometric devices:
one call per device returns everyone at that location. A slow device never
holds the screen; its people just show no punch.
"""
import calendar
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date

from django.conf import settings
from django.utils import timezone

from hrms_app.hrms.utils import call_soap_api
from hrms_app.models import AttendanceStatusColor, DeviceInformation
from hrms_app.services.mobile.attendance_calendar import get_month_calendar
from hrms_app.services.mobile.attendance_codes import LeaveCodes, classify, day_codes
from hrms_app.services.mobile.formatters import employee_code_label, iso_date

logger = logging.getLogger(__name__)

DEVICE_TIMEOUT_SECONDS = 8


def reportees(user):
    return (
        user.employees.filter(is_active=True)
        .select_related("personal_detail", "device_location")
        .order_by("first_name", "last_name")
    )


def _member(user, build_url, *, is_self=False):
    details = getattr(user, "personal_detail", None)
    avatar = getattr(details, "avatar", None)
    return {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        "code": employee_code_label(user.username),
        "avatar_url": build_url(avatar.url) if avatar else None,
        "is_self": is_self,
    }


def _punched_today(users, today):
    """(user ids with a punch today, did every device answer)."""
    by_location = defaultdict(list)
    for user in users:
        code = getattr(getattr(user, "personal_detail", None), "employee_code", None)
        if user.device_location_id and code:
            by_location[user.device_location_id].append((user.pk, code))
    if not by_location:
        return set(), False

    devices = DeviceInformation.objects.filter(device_location_id__in=by_location)
    executor = ThreadPoolExecutor(max_workers=max(len(by_location), 1))
    calls = {
        executor.submit(call_soap_api, device, f"{today} 00:01", f"{today} 23:59"): device.device_location_id
        for device in devices
    }
    done, pending = wait(calls, timeout=DEVICE_TIMEOUT_SECONDS)
    executor.shutdown(wait=False)

    punched, all_answered = set(), not pending and len(calls) == len(by_location)
    for call in done:
        try:
            result = call.result()
        except Exception:
            logger.exception("Biometric device call failed")
            result = None
        if result is None:
            all_answered = False
            continue
        for user_id, code in by_location[calls[call]]:
            if (result.get(code) or {}).get(today):
                punched.add(user_id)
    return punched, all_answered


def _today_category(code, punched, leave_codes):
    """The planned day wins; otherwise a punch decides."""
    category = classify(code, leave_codes) if code else None
    if category in ("leave", "tour", "holiday", "off"):
        return category
    return "present" if punched else "not_in"


def get_team_today(user):
    team = list(reportees(user))
    if not team:
        return {"has_team": False}

    today = timezone.localdate()
    leave_codes = LeaveCodes.load()
    punched, device_ok = _punched_today(team, today)
    counts = dict.fromkeys(("present", "leave", "tour", "not_in", "off"), 0)
    for member in team:
        code = day_codes(member, today, today, today=today)[today][0]
        category = _today_category(code, member.pk in punched, leave_codes)
        counts["off" if category == "holiday" else category] += 1
    return {
        "has_team": True,
        "total": len(team),
        "device_available": device_ok,
        **counts,
    }


def get_team_month(user, year, month, build_url):
    today = timezone.localdate()
    start, end = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    team = list(reportees(user))
    shows_today = start <= today <= end
    punched = _punched_today(team, today)[0] if shows_today else set()
    present_color = (
        AttendanceStatusColor.objects.filter(status=settings.PRESENT).values_list("color_hex", flat=True).first()
    )

    def row(member, is_self=False):
        codes = day_codes(member, start, end, today=today)
        days = []
        for day, (code, color) in sorted(codes.items()):
            if day == today and member.pk in punched and not code:
                code, color = "P", present_color
            days.append({"date": iso_date(day), "code": code, "color": color})
        return {**_member(member, build_url, is_self=is_self), "days": days}

    return {
        "year": year,
        "month": month,
        "today": iso_date(today),
        "members": [row(user, is_self=True), *(row(member) for member in team)],
    }


def get_member_day(user, member_id, day):
    """One reportee's day for the detail sheet, or None if they aren't one."""
    if member_id == user.pk:
        member = user
    else:
        member = reportees(user).filter(pk=member_id).first()
    if member is None:
        return None
    month = get_month_calendar(member, day.year, day.month)
    found = next(item for item in month["days"] if item["date"] == day.isoformat())
    return {"name": member.get_full_name() or member.username, "day": found}
