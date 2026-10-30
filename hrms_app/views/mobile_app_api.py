"""Mobile app meta endpoints (no login needed)."""
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.models import AppSetting

# Managed from Django admin -> Application Settings (no deploy needed):
#   ANDROID_LATEST_VERSION   e.g. 1.2.0   -> "update available" snackbar
#   ANDROID_MIN_VERSION      e.g. 1.0.0   -> older apps get a persistent "must update"
#   ANDROID_UPDATE_URL       Play Store / APK link opened by the Update button
#   ANDROID_RELEASE_NOTES    optional one-liner shown in the snackbar
_KEYS = {
    "latest_version": "LATEST_VERSION",
    "min_version": "MIN_VERSION",
    "update_url": "UPDATE_URL",
    "release_notes": "RELEASE_NOTES",
}
_PLATFORMS = {"android", "ios"}


class AppVersionAPIView(APIView):
    """GET /api/v1/app/version/?platform=android"""

    permission_classes = [AllowAny]
    # Public: an expired token in the header must not turn this into a 401.
    authentication_classes = []

    def get(self, request):
        platform = request.query_params.get("platform", "android").lower()
        if platform not in _PLATFORMS:
            return create_response("error", "Unknown platform.", status_code=400)

        prefix = f"{platform.upper()}_"
        values = dict(
            AppSetting.objects.filter(key__in=[prefix + key for key in _KEYS.values()])
            .values_list("key", "value")
        )
        data = {field: (values.get(prefix + key) or "").strip() or None for field, key in _KEYS.items()}
        return create_response("success", "App version fetched successfully.", data)
