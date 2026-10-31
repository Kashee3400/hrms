"""Attendance calendar for the mobile app (JWT auth)."""
import logging
from datetime import date

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile import team_attendance
from hrms_app.services.mobile.attendance_calendar import get_month_calendar
from hrms_app.services.mobile.holidays import get_holidays

logger = logging.getLogger(__name__)


class TeamTodayView(APIView):
    """GET /api/v1/attendance/team/today/ - today's headcount of direct reportees."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return create_response("success", "Team today.", team_attendance.get_team_today(request.user))


class TeamMonthView(APIView):
    """GET /api/v1/attendance/team/?year=&month= - the month grid of direct reportees."""

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
        data = team_attendance.get_team_month(request.user, year, month, request.build_absolute_uri)
        return create_response("success", "Team attendance.", data)


class TeamMemberDayView(APIView):
    """GET /api/v1/attendance/team/<id>/day/?date=YYYY-MM-DD - one reportee's day."""

    permission_classes = [IsAuthenticated]

    def get(self, request, member_id):
        try:
            day = date.fromisoformat(request.query_params.get("date", ""))
        except ValueError:
            return create_response("error", "Enter a valid date.", status_code=400)
        data = team_attendance.get_member_day(request.user, member_id, day)
        if data is None:
            return create_response("error", "Employee not found in your team.", status_code=404)
        return create_response("success", "Team member day.", data)


class HolidayListView(APIView):
    """GET /api/v1/holiday/list/?year=2026 (default: this year)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
        except ValueError:
            return create_response("error", "year must be a number.", status_code=400)
        if not 2000 <= year <= today.year + 1:
            return create_response("error", "Invalid year.", status_code=400)
        return create_response("success", "Holidays.", get_holidays(request.user, year))


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
