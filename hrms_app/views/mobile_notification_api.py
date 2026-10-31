"""The Notifications screen for the mobile app (JWT auth)."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile import notifications
from hrms_app.views.mobile_leave_api import _error, _int_param


class NotificationFeedView(APIView):
    """GET /api/v1/notifications/feed/?filter=all|unread|leave|tour|attendance&page="""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = notifications.get_feed(
            request.user,
            filter_by=request.query_params.get("filter") or "all",
            page=_int_param(request, "page", 1),
        )
        return create_response("success", "Notifications.", data)


class NotificationReadView(APIView):
    """POST /api/v1/notifications/feed/<id>/read/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        if not notifications.mark_read(request.user, notification_id):
            return _error({"__all__": ["Notification not found."]}, status.HTTP_404_NOT_FOUND)
        return create_response("success", "Marked as read.", None)


class NotificationReadAllView(APIView):
    """POST /api/v1/notifications/feed/read-all/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        notifications.mark_all_read(request.user)
        return create_response("success", "All marked as read.", None)
