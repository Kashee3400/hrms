"""Marking a day Present for superusers in the mobile app (JWT auth)."""
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services import attendance_marking
from hrms_app.views.mobile_leave_api import _error
from hrms_app.views.mobile_settings_api import IsSuperuser


def _parse(data):
    """(employee, date, error response)."""
    try:
        day = date.fromisoformat(str(data.get("date") or ""))
    except ValueError:
        return None, None, _error({"__all__": ["Select a valid date."]}, status.HTTP_400_BAD_REQUEST)
    user_id = str(data.get("user_id") or "")
    user = get_user_model().objects.filter(pk=user_id).first() if user_id.isdigit() else None
    if user is None:
        return None, None, _error({"__all__": ["Select an employee."]}, status.HTTP_400_BAD_REQUEST)
    return user, day, None


class AttendanceMarkView(APIView):
    """GET  /api/v1/attendance/mark/?user_id=&date= - the day and what can be done.
    POST /api/v1/attendance/mark/ {user_id, date, kind, reason}"""

    permission_classes = [IsAuthenticated, IsSuperuser]

    def get(self, request):
        user, day, error = _parse(request.query_params)
        if error:
            return error
        return create_response("success", "Attendance day.", attendance_marking.get_day(user, day))

    def post(self, request):
        user, day, error = _parse(request.data)
        if error:
            return error
        problem = attendance_marking.mark(
            request.user, user, day, request.data.get("kind"), request.data.get("reason")
        )
        if problem:
            return _error({"__all__": [problem]}, status.HTTP_400_BAD_REQUEST)
        return create_response("success", "Attendance marked.", attendance_marking.get_day(user, day))
