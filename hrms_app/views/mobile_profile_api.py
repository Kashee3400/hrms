"""The employee's own profile for the mobile app (JWT auth)."""
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile import profile
from hrms_app.views.mobile_leave_api import _error


def _profile_response(request, message):
    return create_response("success", message, profile.get_profile(request.user, request.build_absolute_uri))


class ProfileView(APIView):
    """GET /api/v1/profile/ - details, addresses and the edit form's choices."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return _profile_response(request, "Profile.")


class ProfileDetailsView(APIView):
    """PUT /api/v1/profile/details/ - what an employee may change themselves."""

    permission_classes = [IsAuthenticated]

    def put(self, request):
        if not request.user.has_perm(profile.EDIT_PERMISSION):
            return _error({"__all__": ["You can't edit your details. Please contact HR."]}, status.HTTP_403_FORBIDDEN)
        errors = profile.update_details(request.user, request.data)
        return _error(errors) if errors else _profile_response(request, "Personal details updated.")


class ProfileAddressView(APIView):
    """PUT /api/v1/profile/address/<permanent|correspondence>/"""

    permission_classes = [IsAuthenticated]

    def put(self, request, kind):
        if kind not in profile.ADDRESSES:
            return _error({"__all__": ["Address not found."]}, status.HTTP_404_NOT_FOUND)
        errors = profile.update_address(request.user, kind, request.data)
        return _error(errors) if errors else _profile_response(request, "Address updated.")


class ProfileAvatarView(APIView):
    """POST /api/v1/profile/avatar/ - multipart `avatar`; cropped to a square."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        errors = profile.update_avatar(request.user, request.FILES.get("avatar"))
        return _error(errors) if errors else _profile_response(request, "Photo updated.")


class ChangePasswordView(APIView):
    """POST /api/v1/profile/change-password/ {old_password, new_password1, new_password2}"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        errors = profile.change_password(request.user, request.data)
        if errors:
            return _error(errors)
        return create_response("success", "Password changed. Please sign in again.", None)
