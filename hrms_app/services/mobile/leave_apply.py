"""
Leave application for the mobile app - same rules as the web form.

Web parity:
- Day counting is a port of static/hrms_app/js/apply_leave.js
  (CL/SL skip Sundays + holidays; same-day leave on a Sunday/holiday is
  refused; half-day adjustments table).
- "Apply" is blocked when balance - booked < 0, except LWP (the web
  disables the button). The real balance check happens at approval.
- Saving goes through the web's LeaveApplicationForm, so every policy in
  LeavePolicyManager and the form's own checks run unchanged.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import escape, linebreaks

from hrms_app.forms.leave_form import LeaveApplicationForm
from hrms_app.models import Holiday, LeaveBalanceOpenings, LeaveType
from hrms_app.services.leave_balance_summary import get_dashboard_leave_balances
from hrms_app.services import attendance_lock
from hrms_app.services.leave_service import LeaveDomainService
from hrms_app.utility.leave_utils import LeavePolicyManager

LWP_CODE = "LWP"
# Short leave has its own time-based form (services/mobile/short_leave.py);
# it is listed in the options but never goes through the day-based flow.
SHORT_LEAVE_CODE = "STL"
# CL and SL don't count Sundays/holidays inside the range (apply_leave.js).
OFF_DAY_EXCLUDED_CODES = {"CL", "SL"}
SL_ATTACHMENT_ABOVE_DAYS = 5
APPLY_PERMISSION = "hrms_app.add_leaveapplication"

FULL, FIRST_HALF, SECOND_HALF = settings.FULL_DAY, settings.FIRST_HALF, settings.SECOND_HALF
START_CHOICES = {FULL, FIRST_HALF, SECOND_HALF}
END_CHOICES = {FULL, FIRST_HALF}

# (start choice, end choice) -> adjustment, from apply_leave.js
_RANGE_ADJUSTMENTS = {
    (FULL, FULL): 0,
    (FIRST_HALF, FIRST_HALF): -0.5,
    (SECOND_HALF, FIRST_HALF): -1,
    (SECOND_HALF, FULL): -0.5,
    (FULL, FIRST_HALF): -0.5,
}


def available_balance(user, leave_type):
    """Balance shown on the web apply page ("rem_bal")."""
    return LeaveDomainService.get_remaining_balance(
        user=user, leave_type=leave_type, target_date=timezone.localdate()
    )


def can_apply_with(code, available):
    return code == LWP_CODE or available > 0


# ─────────────────────────────────────────────────────────────
# Apply options
# ─────────────────────────────────────────────────────────────


def _option(user, leave_type, color):
    code = leave_type.leave_type_short_code
    available = available_balance(user, leave_type)
    is_short = code == SHORT_LEAVE_CODE
    return {
        "id": leave_type.pk,
        "name": leave_type.leave_type,
        "code": code,
        "color": color or leave_type.color_hex,
        "available": available,
        # STL balance depends on the chosen date's month; its own preview
        # checks it, so the type is always selectable.
        "can_apply": is_short or can_apply_with(code, available),
        "is_lwp": code == LWP_CODE,
        "is_short_leave": is_short,
        "allow_half_day": leave_type.allow_half_day,
        "skips_off_days": code in OFF_DAY_EXCLUDED_CODES,
        "attachment_required_above_days": SL_ATTACHMENT_ABOVE_DAYS if code == "SL" else None,
        "min_notice_days": leave_type.min_notice_days,
        "min_days": leave_type.min_days_limit,
        "max_days": leave_type.max_days_limit,
    }


def get_apply_options(user):
    """Leave types the user can see on the web leave cards, with rules."""
    seen = set()
    types = []
    for row in get_dashboard_leave_balances(user):
        leave_type = row["leave_type"]
        if leave_type.pk in seen:
            continue
        seen.add(leave_type.pk)
        types.append(_option(user, leave_type, row["color"]))

    # STL balances are monthly: the web card only shows when this month's row
    # exists, but a short leave can be for an earlier month this year.
    stl = LeaveType.objects.filter(leave_type_short_code=SHORT_LEAVE_CODE).first()
    if (
        stl
        and stl.pk not in seen
        and LeaveBalanceOpenings.objects.filter(
            user=user, leave_type=stl, year=timezone.localdate().year, is_active=True
        ).exists()
    ):
        types.append(_option(user, stl, None))

    manager = user.reports_to
    designation = getattr(getattr(manager, "personal_detail", None), "designation", None)
    return {
        "can_apply_leave": user.has_perm(APPLY_PERMISSION),
        "reporting_manager": (
            {"name": manager.get_full_name() or manager.username, "designation": str(designation) if designation else None}
            if manager
            else None
        ),
        "leave_types": types,
    }


# ─────────────────────────────────────────────────────────────
# Day breakdown (port of apply_leave.js)
# ─────────────────────────────────────────────────────────────


@dataclass
class Breakdown:
    days: list = field(default_factory=list)
    total: float = 0
    error: str = None


def _holiday_titles(start, end):
    # Same query as the web (/api/v1/holidays/?start_date=&end_date=), keyed by start date.
    return dict(
        Holiday.objects.filter(start_date__gte=start, end_date__lte=end).values_list(
            "start_date", "title"
        )
    )


def compute_breakdown(leave_type, start, end, start_choice, end_choice):
    holidays = _holiday_titles(start, end)
    skips_off_days = leave_type.leave_type_short_code in OFF_DAY_EXCLUDED_CODES
    single_day = start == end

    if single_day and (start.weekday() == 6 or start in holidays):
        return Breakdown(error="Selected date is either a Sunday or a Holiday. Leave cannot be applied.")

    days, base = [], 0
    current = start
    while current <= end:
        is_sunday = current.weekday() == 6
        holiday = holidays.get(current)
        is_off = bool(is_sunday or holiday)
        counted = not (skips_off_days and is_off)
        base += 1 if counted else 0
        role = "single" if single_day else "start" if current == start else "end" if current == end else "middle"
        days.append(
            {
                "date": current.isoformat(),
                "role": role,
                "is_sunday": is_sunday,
                "holiday": holiday,
                "counted": counted,
            }
        )
        current += timedelta(days=1)

    if single_day:
        adjustment = 0 if start_choice == FULL and base >= 1 else -0.5
    else:
        adjustment = _RANGE_ADJUSTMENTS.get((start_choice, end_choice), 0)

    total = base + adjustment
    if total < 0:
        return Breakdown(days=days, error="Insufficient leave balance for this request.")
    return Breakdown(days=days, total=total)


# ─────────────────────────────────────────────────────────────
# Input parsing
# ─────────────────────────────────────────────────────────────


@dataclass
class LeaveInput:
    leave_type: LeaveType
    start: date
    end: date
    start_choice: str
    end_choice: str


def parse_input(user, data):
    """Returns (LeaveInput, None) or (None, {field: message})."""
    errors = {}
    leave_type = LeaveType.objects.filter(pk=data.get("leave_type")).first()
    if leave_type is None:
        errors["leave_type"] = "Select a valid leave type."
    elif leave_type.leave_type_short_code == SHORT_LEAVE_CODE:
        errors["leave_type"] = "Short leave uses the short leave form."

    def parse_date(key):
        try:
            return date.fromisoformat(str(data.get(key, "")))
        except ValueError:
            errors[key] = "Enter a valid date (YYYY-MM-DD)."
            return None

    start, end = parse_date("start_date"), parse_date("end_date")
    if start and end and start > end:
        errors["end_date"] = "End Date must be after Start Date."

    start_choice = str(data.get("start_day_choice") or FULL)
    end_choice = str(data.get("end_day_choice") or FULL)
    if start and end and start == end:
        end_choice = start_choice  # the web keeps both selects in sync for one day
    if start_choice not in START_CHOICES:
        errors["start_day_choice"] = "Invalid start day choice."
    if end_choice not in END_CHOICES and not (start == end and end_choice in START_CHOICES):
        errors["end_day_choice"] = "Invalid end day choice."
    # Half-day rules per type (e.g. EL) are enforced by LeavePolicyManager, as on the web.

    if errors:
        return None, errors
    return LeaveInput(leave_type, start, end, start_choice, end_choice), None


def _aware(day):
    return timezone.make_aware(datetime.combine(day, time.min))


# ─────────────────────────────────────────────────────────────
# Preview & submit
# ─────────────────────────────────────────────────────────────


def preview(user, leave_input):
    """Everything the form needs before submitting, including policy errors."""
    li = leave_input
    breakdown = compute_breakdown(li.leave_type, li.start, li.end, li.start_choice, li.end_choice)
    available = available_balance(user, li.leave_type)
    projected = available - breakdown.total
    code = li.leave_type.leave_type_short_code

    errors = [breakdown.error] if breakdown.error else []
    lock = attendance_lock.active_lock(li.start, li.end)
    if lock:
        errors.insert(0, attendance_lock.lock_message(lock))
    if not breakdown.error:
        try:
            LeavePolicyManager(
                user=user,
                leave_type=li.leave_type,
                start_date=_aware(li.start),
                end_date=_aware(li.end),
                start_day_choice=li.start_choice,
                end_day_choice=li.end_choice,
                bookedLeave=breakdown.total,
            ).validate_policies()
        except ValidationError as exc:
            errors.extend(exc.messages)

    balance_ok = code == LWP_CODE or projected >= 0
    return {
        "leave_type_id": li.leave_type.pk,
        "days": breakdown.days,
        "total_days": breakdown.total,
        "available": available,
        "projected": projected,
        "balance_ok": balance_ok,
        "attachment_required": code == "SL" and breakdown.total > SL_ATTACHMENT_ABOVE_DAYS,
        "errors": errors,
        "can_submit": not errors and balance_ok and breakdown.total > 0,
    }


def submit(user, leave_input, *, leave_address, reason, attachment=None):
    """Saves through the web form. Returns (application, None) or (None, errors)."""
    li = leave_input
    summary = preview(user, li)
    if summary["errors"]:
        return None, {"__all__": summary["errors"]}
    if not summary["balance_ok"]:
        return None, {"__all__": ["Insufficient leave balance for this request."]}

    form = LeaveApplicationForm(
        data={
            "leave_type": li.leave_type.pk,
            "startDate": li.start.isoformat(),
            "endDate": li.end.isoformat(),
            "startDayChoice": li.start_choice,
            "endDayChoice": li.end_choice,
            "usedLeave": summary["total_days"],
            "balanceLeave": summary["projected"],
            "leave_address": (leave_address or "").strip(),
            # The web field is CKEditor (HTML); keep line breaks, escape markup.
            "reason": linebreaks(escape((reason or "").strip())) if (reason or "").strip() else "",
        },
        files={"attachment": attachment} if attachment else None,
        user=user,
        leave_type=li.leave_type.pk,
    )
    if not form.is_valid():
        return None, {key: [str(m) for m in msgs] for key, msgs in form.errors.items()}

    application = form.save(commit=False)
    application.appliedBy = user
    if attachment:
        application.attachment = attachment
    application.save()
    return application, None
