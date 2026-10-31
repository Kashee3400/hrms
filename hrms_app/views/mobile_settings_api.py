"""Application Settings for superusers in the mobile app (JWT auth)."""
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile import app_settings
from hrms_app.views.mobile_leave_api import _error


class IsSuperuser(BasePermission):
    message = "Only a superuser can change application settings."

    def has_permission(self, request, view):
        return request.user.is_superuser


class AppSettingListView(APIView):
    """GET /api/v1/app-settings/ - every setting and the employee list."""

    permission_classes = [IsAuthenticated, IsSuperuser]

    def get(self, request):
        return create_response("success", "Application settings.", app_settings.get_settings())


class AppSettingDetailView(APIView):
    """PUT /api/v1/app-settings/<key>/ {value, beyond_policy, allowed_users}"""

    permission_classes = [IsAuthenticated, IsSuperuser]

    def put(self, request, key):
        setting, error = app_settings.update_setting(request.user, key, request.data)
        if error:
            return _error({"__all__": [error]}, status.HTTP_400_BAD_REQUEST)
        return create_response("success", "Setting saved.", setting)
