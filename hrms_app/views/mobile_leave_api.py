"""Leave application endpoints for the mobile app (JWT auth)."""
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from hrms_app.hrms.utils import create_response
from hrms_app.services.mobile import leave_apply, my_leaves, team_leaves


def _error(errors, http_status=status.HTTP_400_BAD_REQUEST):
    """`{status, message, errors}`; message = first error, for a snackbar."""
    flat = [msg for msgs in errors.values() for msg in (msgs if isinstance(msgs, list) else [msgs])]
    return Response(
        {
            "status": "error",
            "message": flat[0] if flat else "Please check the details.",
            "errors": {key: (msgs if isinstance(msgs, list) else [msgs]) for key, msgs in errors.items()},
        },
        status=http_status,
    )


class LeaveApplyOptionsView(APIView):
    """GET /api/v1/leave/apply-options/ - leave types, balances, rules, manager."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return create_response(
            "success", "Leave options fetched.", leave_apply.get_apply_options(request.user)
        )


class LeavePreviewView(APIView):
    """POST /api/v1/leave/preview/ - day breakdown, balance impact, policy errors.

    Body: {leave_type, start_date, end_date, start_day_choice, end_day_choice}
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        leave_input, errors = leave_apply.parse_input(request.user, request.data)
        if errors:
            return _error(errors)
        return create_response(
            "success", "Leave preview.", leave_apply.preview(request.user, leave_input)
        )


class LeaveApplyView(APIView):
    """POST /api/v1/leave/apply/ - multipart (attachment) or JSON.

    Body: preview fields + leave_address, reason, attachment (SL > 5 days).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if not request.user.has_perm(leave_apply.APPLY_PERMISSION):
            return _error({"__all__": ["You do not have permission to apply for leave."]}, status.HTTP_403_FORBIDDEN)

        leave_input, errors = leave_apply.parse_input(request.user, request.data)
        if errors:
            return _error(errors)

        application, errors = leave_apply.submit(
            request.user,
            leave_input,
            leave_address=request.data.get("leave_address"),
            reason=request.data.get("reason"),
            attachment=request.FILES.get("attachment"),
        )
        if errors:
            return _error(errors)

        return create_response(
            "success",
            "Leave applied successfully. Sent to your manager for approval.",
            {
                "id": application.pk,
                "application_no": application.applicationNo,
                "slug": application.slug,
                "status": application.status,
                "used_leave": application.usedLeave,
            },
            status.HTTP_201_CREATED,
        )


def _int_param(request, name, default=None):
    try:
        return int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default


class MyLeaveOverviewView(APIView):
    """GET /api/v1/leave/overview/?year=2026 - balances + this year's counts."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = _int_param(request, "year", timezone.localdate().year)
        return create_response("success", "Leave overview.", my_leaves.get_overview(request.user, year))


class MyLeaveListView(APIView):
    """GET /api/v1/leave/my/?year=&status=pending|approved|rejected|cancelled&leave_type=&page="""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = my_leaves.list_leaves(
            request.user,
            year=_int_param(request, "year", timezone.localdate().year),
            status=request.query_params.get("status") or None,
            leave_type=_int_param(request, "leave_type"),
            page=_int_param(request, "page", 1),
        )
        return create_response("success", "Leave applications.", data)


class MyLeaveDetailView(APIView):
    """GET / DELETE /api/v1/leave/my/<id>/ (own applications only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, leave_id):
        leave = my_leaves.get_leave(request.user, leave_id)
        if leave is None:
            return _error({"__all__": ["Leave application not found."]}, status.HTTP_404_NOT_FOUND)
        return create_response(
            "success",
            "Leave application.",
            my_leaves.leave_detail(request.user, leave, request.build_absolute_uri),
        )

    def delete(self, request, leave_id):
        leave = my_leaves.get_leave(request.user, leave_id)
        if leave is None:
            return _error({"__all__": ["Leave application not found."]}, status.HTTP_404_NOT_FOUND)
        if not my_leaves.delete_leave(request.user, leave):
            return _error(
                {"__all__": ["Only pending, rejected or cancelled applications can be deleted."]},
                status.HTTP_403_FORBIDDEN,
            )
        return create_response("success", "Leave application deleted.", None)


class MyLeaveCancelView(APIView):
    """POST /api/v1/leave/my/<id>/cancel/ - ask the manager to cancel an approved leave."""

    permission_classes = [IsAuthenticated]

    def post(self, request, leave_id):
        leave = my_leaves.get_leave(request.user, leave_id)
        if leave is None:
            return _error({"__all__": ["Leave application not found."]}, status.HTTP_404_NOT_FOUND)
        if not my_leaves.request_cancellation(request.user, leave):
            return _error(
                {"__all__": ["Only approved leave can be cancelled."]}, status.HTTP_403_FORBIDDEN
            )
        return create_response(
            "success",
            "Cancellation requested. Your manager will review it.",
            my_leaves.leave_item(request.user, leave),
        )


# ─────────────────────────────────────────────────────────────
# Team leaves (reviewers)
# ─────────────────────────────────────────────────────────────


class _ReviewerView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        from hrms_app.services.leave_approval import is_leave_reviewer

        if not is_leave_reviewer(request.user):
            self.permission_denied(request, message="Only reporting managers can review leave.")


class TeamLeaveListView(_ReviewerView):
    """GET /api/v1/leave/team/?status=pending|approved|rejected|cancelled|all&year=&q=&page=

    `pending` (default) is the review queue: pending, cancellation requests
    and, for the admin department, recommended LWP.
    """

    def get(self, request):
        data = team_leaves.list_team_leaves(
            request.user,
            status=request.query_params.get("status") or "pending",
            year=_int_param(request, "year", timezone.localdate().year),
            search=(request.query_params.get("q") or "").strip(),
            page=_int_param(request, "page", 1),
            build_url=request.build_absolute_uri,
        )
        return create_response("success", "Team leave applications.", data)


class TeamLeaveDetailView(_ReviewerView):
    """GET /api/v1/leave/team/<id>/ - detail + applicant balance + allowed actions."""

    def get(self, request, leave_id):
        leave = team_leaves.get_team_leave(request.user, leave_id)
        if leave is None:
            return _error({"__all__": ["Leave application not found."]}, status.HTTP_404_NOT_FOUND)
        return create_response(
            "success",
            "Team leave application.",
            team_leaves.team_leave_detail(request.user, leave, request.build_absolute_uri),
        )


class TeamLeaveActionView(_ReviewerView):
    """POST /api/v1/leave/team/<id>/action/ {status, remark}

    `status` must be one of the detail's `allowed_actions`. Approval deducts
    the balance; rejecting/cancelling an approved leave restores it.
    """

    def post(self, request, leave_id):
        leave = team_leaves.get_team_leave(request.user, leave_id)
        if leave is None:
            return _error({"__all__": ["Leave application not found."]}, status.HTTP_404_NOT_FOUND)
        error = team_leaves.act(
            request.user,
            leave,
            (request.data.get("status") or "").strip(),
            request.data.get("remark"),
        )
        if error:
            return _error({"__all__": [error]})
        leave.refresh_from_db()
        return create_response(
            "success",
            f"Leave application {leave.status}.",
            team_leaves.team_leave_detail(request.user, leave, request.build_absolute_uri),
        )
