"""Wishing colleagues from the mobile app (JWT auth)."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.models import CelebrationWish
from hrms_app.services.mobile import celebration_wishes
from hrms_app.views.mobile_leave_api import _error

KINDS = {kind for kind, _ in CelebrationWish.KIND_CHOICES}


class CelebrationWishView(APIView):
    """POST /api/v1/celebrations/wish/ {user_id, kind, message}"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        kind = request.data.get("kind")
        user_id = str(request.data.get("user_id") or "")
        if kind not in KINDS or not user_id.isdigit():
            return _error({"__all__": ["Select whom to wish."]}, status.HTTP_400_BAD_REQUEST)
        problem = celebration_wishes.send_wish(request.user, int(user_id), kind, request.data.get("message"))
        if problem:
            return _error({"__all__": [problem]}, status.HTTP_400_BAD_REQUEST)
        return create_response("success", "Wish sent.", {"kind": kind, "user_id": int(user_id)})


class MyWishesView(APIView):
    """GET /api/v1/celebrations/wishes/?kind=birthday - today's wishes to me."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        kind = request.query_params.get("kind")
        if kind not in KINDS:
            return _error({"__all__": ["Unknown occasion."]}, status.HTTP_400_BAD_REQUEST)
        wishes = celebration_wishes.wishes_received(request.user, kind)
        return create_response("success", "Wishes.", {"wishes": wishes})
