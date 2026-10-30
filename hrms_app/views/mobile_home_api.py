"""Mobile app Home screen endpoints (JWT auth)."""
import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile.home_summary import get_home_summary
from hrms_app.services.mobile.today_attendance import get_today_attendance

logger = logging.getLogger(__name__)


class HomeSummaryAPIView(APIView):
    """GET /api/v1/home/summary/ - balances, tour, month stats, activity."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = get_home_summary(request.user)
        except Exception:
            logger.exception("home summary failed for user %s", request.user.pk)
            return create_response("error", "Could not load home summary.", status_code=500)
        return create_response("success", "Home summary fetched successfully.", data)


class HomeTodayAPIView(APIView):
    """GET /api/v1/home/today/ - today's biometric punches (live from device)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = get_today_attendance(request.user)
        except Exception:
            logger.exception("today attendance failed for user %s", request.user.pk)
            return create_response("error", "Could not load today's attendance.", status_code=500)
        return create_response("success", "Today's attendance fetched successfully.", data)
