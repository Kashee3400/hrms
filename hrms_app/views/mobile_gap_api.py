"""Attendance gaps and approval mails for the mobile app (JWT auth)."""
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from hrms_app.hrms.utils import create_response
from hrms_app.models import AttendanceGap
from hrms_app.services import approval_mail
from hrms_app.services.attendance_gaps import KIND_LABELS, open_groups
from hrms_app.services.mobile.formatters import iso_date
from hrms_app.views.mobile_leave_api import _error


def _group_payload(group, today):
    mail = group.approval_mail
    return {
        "kind": group.kind,
        "label": KIND_LABELS[group.kind],
        "start_date": iso_date(group.start),
        "end_date": iso_date(group.end),
        "days": [iso_date(row.date) for row in group.rows],
        "deadline": iso_date(group.deadline),
        "is_expired": today > group.deadline,
        "is_missing_punch": group.kind == AttendanceGap.MISSING_PUNCH,
        "approval_sent_on": iso_date(timezone.localtime(mail.sent_at).date()) if mail else None,
    }


class AttendanceGapListView(APIView):
    """GET /api/v1/attendance/gaps/ - days the employee still has to act on."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        groups = [_group_payload(group, today) for group in open_groups(request.user)]
        return create_response("success", "Attendance gaps.", {"groups": groups})


class ApprovalMailPreviewView(APIView):
    """POST /api/v1/approval-mail/preview/ {kind, reason, ...} - the mail as it will go."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        mail, error = approval_mail.preview(request.user, request.data)
        if error:
            return _error({"__all__": [error]})
        return create_response("success", "Approval mail preview.", mail)


class ApprovalMailSendView(APIView):
    """POST /api/v1/approval-mail/send/ - same body as the preview."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        error = approval_mail.send(request.user, request.data)
        if error:
            return _error({"__all__": [error]})
        return create_response("success", "Approval mail sent.", None)
