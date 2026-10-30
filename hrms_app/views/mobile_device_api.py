"""FCM device registration for the mobile app (JWT auth)."""
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.models import DeviceToken


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(
        choices=[choice for choice, _ in DeviceToken.PLATFORM_CHOICES], default="android"
    )


class DeviceTokenView(APIView):
    """POST /api/v1/devices/ {token, platform} - register this install.

    A token belongs to one install; if another user logged in on the same
    phone earlier, the token is moved to the current user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return create_response("error", "Invalid device token.", serializer.errors, 400)

        device, created = DeviceToken.objects.update_or_create(
            token=serializer.validated_data["token"],
            defaults={
                "user": request.user,
                "platform": serializer.validated_data["platform"],
                "is_active": True,
            },
        )
        return create_response(
            "success",
            "Device registered." if created else "Device updated.",
            {"id": device.pk},
            201 if created else 200,
        )


class DeviceTokenDetailView(APIView):
    """DELETE /api/v1/devices/<token>/ - unregister on logout (own tokens only)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, token):
        DeviceToken.objects.filter(token=token, user=request.user).update(is_active=False)
        return create_response("success", "Device unregistered.", None)
