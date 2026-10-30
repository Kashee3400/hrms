"""
Today's punches for the mobile Home card (``GET /api/v1/home/today/``).

Punches are read live from the biometric device's SOAP API, the same source
as the web dashboard (``attendanceutils.get_check_in_out_times``). That call
has no timeout of its own, so it runs in a worker thread with a deadline:
a slow device never blocks the app.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timedelta

from django.utils import timezone

from hrms_app.hrms.utils import call_soap_api
from hrms_app.models import DeviceInformation
from hrms_app.services.mobile.formatters import shift_payload

logger = logging.getLogger(__name__)

DEVICE_TIMEOUT_SECONDS = 8


def _fetch_punches(device, emp_code, day):
    """Returns the sorted punch datetimes (naive, local) for ``day``."""
    result = call_soap_api(
        device_instance=device,
        from_date=f"{day} 00:01",
        to_date=f"{day} 23:59",
    )
    punches = (result or {}).get(emp_code, {}).get(day) or []
    return sorted(punches)


def _punches_with_deadline(user, day):
    """(punches, device_ok). DB lookups stay on this thread; only the SOAP
    request runs in the worker so no DB connection is opened there."""
    emp_code = getattr(getattr(user, "personal_detail", None), "employee_code", None)
    device = (
        DeviceInformation.objects.filter(device_location=user.device_location).first()
        if user.device_location_id
        else None
    )
    if not device or not emp_code:
        return [], False

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_fetch_punches, device, emp_code, day)
    try:
        return future.result(timeout=DEVICE_TIMEOUT_SECONDS), True
    except FutureTimeout:
        logger.warning("Biometric device timed out for user %s", user.pk)
        return [], False
    except Exception:
        logger.exception("Biometric device call failed for user %s", user.pk)
        return [], False
    finally:
        executor.shutdown(wait=False)


def _minutes(delta):
    return max(int(delta.total_seconds() // 60), 0)


def get_today_attendance(user):
    now = timezone.localtime()
    today = now.date()
    shift = shift_payload(user)
    punches, device_ok = _punches_with_deadline(user, today)

    first_in = punches[0] if punches else None
    last_out = punches[-1] if len(punches) > 1 else None

    shift_minutes = None
    expected_out = None
    status = "not_punched"
    late_by = 0

    if shift:
        start = datetime.strptime(shift["start_time"], "%H:%M")
        end = datetime.strptime(shift["end_time"], "%H:%M")
        shift_minutes = _minutes(end - start)

    if first_in:
        if shift_minutes is not None:
            expected_out = first_in + timedelta(minutes=shift_minutes)
        status = "on_time"
        if shift and shift["grace_till"]:
            grace = datetime.strptime(shift["grace_till"], "%H:%M").time()
            if first_in.time() > grace:
                status = "late"
                shift_start = datetime.combine(today, datetime.strptime(shift["start_time"], "%H:%M").time())
                late_by = _minutes(first_in - shift_start)

    # Without a punch-out yet, "worked" counts up to now.
    worked_until = last_out or (now.replace(tzinfo=None) if first_in else None)
    worked_minutes = _minutes(worked_until - first_in) if first_in else 0

    def aware(dt):
        return timezone.make_aware(dt).isoformat() if dt else None

    location = user.device_location
    return {
        "date": today.isoformat(),
        "device_location": location.location_name if location else None,
        "device_available": device_ok,
        "first_in": aware(first_in),
        "last_out": aware(last_out),
        "expected_out": aware(expected_out),
        "punch_count": len(punches),
        "worked_minutes": worked_minutes,
        "shift_minutes": shift_minutes,
        "status": status,
        "late_by_minutes": late_by,
        "shift": shift,
        "synced_at": now.isoformat(),
    }
