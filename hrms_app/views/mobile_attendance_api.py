"""Attendance calendar for the mobile app (JWT auth)."""
import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile.attendance_calendar import get_month_calendar

logger = logging.getLogger(__name__)


class AttendanceCalendarView(APIView):
    """GET /api/v1/attendance/calendar/?year=2026&month=10 (defaults: this month)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            return create_response("error", "year and month must be numbers.", status_code=400)
        if not (1 <= month <= 12 and 2000 <= year <= today.year + 1):
            return create_response("error", "Invalid year or month.", status_code=400)

        try:
            data = get_month_calendar(request.user, year, month)
        except Exception:
            logger.exception("attendance calendar failed for user %s", request.user.pk)
            return create_response("error", "Could not load the attendance calendar.", status_code=500)
        return create_response("success", "Attendance calendar.", data)
