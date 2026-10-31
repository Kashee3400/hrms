"""Tour endpoints for the mobile app (JWT auth)."""
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from django.utils import timezone

from hrms_app.hrms.utils import create_response
from hrms_app.services import tour_approval
from hrms_app.services.leave_approval import is_leave_reviewer
from hrms_app.services.mobile import team_tours, tours
from hrms_app.views.mobile_leave_api import _error, _int_param
from hrms_app.views.tour_views import render_tour_pdf

_NOT_FOUND = {"__all__": ["Tour not found."]}


class TourApplyOptionsView(APIView):
    """GET /api/v1/tour/apply-options/ - approval types, sanctioning authority."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return create_response("success", "Tour options fetched.", tours.get_apply_options(request.user))


class TourOverviewView(APIView):
    """GET /api/v1/tour/overview/?year=2026 - this year's counts + the active tour."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = _int_param(request, "year", timezone.localdate().year)
        return create_response("success", "Tour overview.", tours.get_overview(request.user, year))


class MyTourListView(APIView):
    """GET  /api/v1/tour/my/?year=&status=pending|approved|rejected|cancelled&page=
    POST /api/v1/tour/my/ - apply (same rules as the web's TourForm).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = tours.list_tours(
            request.user,
            year=_int_param(request, "year", timezone.localdate().year),
            status=request.query_params.get("status"),
            page=_int_param(request, "page", 1),
        )
        return create_response("success", "Tours.", data)

    def post(self, request):
        if not request.user.has_perm(tours.ADD_PERMISSION):
            return _error({"__all__": ["You can't apply for a tour."]}, status.HTTP_403_FORBIDDEN)
        tour, errors = tours.save_tour(request.user, request.data)
        if errors:
            return _error(errors)
        return create_response(
            "success",
            "Tour applied.",
            tours.tour_detail(request.user, tour, request.build_absolute_uri),
            status.HTTP_201_CREATED,
        )


class MyTourDetailView(APIView):
    """GET / PUT / DELETE /api/v1/tour/my/<id>/ (PUT and DELETE while pending)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, tour_id):
        tour = tours.get_own_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        return create_response(
            "success", "Tour.", tours.tour_detail(request.user, tour, request.build_absolute_uri)
        )

    def put(self, request, tour_id):
        tour = tours.get_own_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        if not tours.tour_item(request.user, tour)["can_edit"]:
            return _error({"__all__": ["Only a pending tour can be edited."]})
        tour, errors = tours.save_tour(request.user, request.data, instance=tour)
        if errors:
            return _error(errors)
        return create_response(
            "success", "Tour updated.", tours.tour_detail(request.user, tour, request.build_absolute_uri)
        )

    def delete(self, request, tour_id):
        tour = tours.get_own_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        error = tours.delete_tour(request.user, tour)
        if error:
            return _error({"__all__": [error]})
        return create_response("success", "Tour deleted.", None)


class MyTourCancelView(APIView):
    """POST /api/v1/tour/my/<id>/cancel/ {reason} - approved -> pending cancellation."""

    permission_classes = [IsAuthenticated]

    def post(self, request, tour_id):
        tour = tours.get_own_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        error = tours.request_cancellation(request.user, tour, request.data.get("reason"))
        if error:
            return _error({"__all__": [error]})
        return create_response(
            "success",
            "Cancellation requested.",
            tours.tour_detail(request.user, tour, request.build_absolute_uri),
        )


class MyTourRerequestView(APIView):
    """POST /api/v1/tour/my/<id>/rerequest/ {start_time, end_date, end_time, reason}

    Approved or rejected tour -> new schedule, back to pending for the manager.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, tour_id):
        tour = tours.get_own_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        tour, errors = tours.rerequest_tour(request.user, tour, request.data)
        if errors:
            return _error(errors)
        return create_response(
            "success",
            "Tour sent for approval again.",
            tours.tour_detail(request.user, tour, request.build_absolute_uri),
        )


class TourPdfView(APIView):
    """GET /api/v1/tour/pdf/<token>/ - the app opens the PDF in the browser,
    which has no login, so the detail payload gives a short-lived signed link."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        tour = tours.tour_from_pdf_token(token)
        if tour is None:
            return _error({"__all__": ["This link has expired. Open the tour again."]}, status.HTTP_404_NOT_FOUND)
        return render_tour_pdf(request, tour)


class _ReviewerView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not is_leave_reviewer(request.user):
            self.permission_denied(request, message="Only reporting managers can review tours.")


class TeamTourListView(_ReviewerView):
    """GET /api/v1/tour/team/?status=pending|approved|rejected|cancelled|all&year=&q=&page="""

    def get(self, request):
        data = team_tours.list_team_tours(
            request.user,
            status=request.query_params.get("status") or "pending",
            year=_int_param(request, "year", timezone.localdate().year),
            search=(request.query_params.get("q") or "").strip(),
            page=_int_param(request, "page", 1),
            build_url=request.build_absolute_uri,
        )
        return create_response("success", "Team tours.", data)


class TeamTourDetailView(_ReviewerView):
    """GET /api/v1/tour/team/<id>/ - detail + applicant + allowed actions."""

    def get(self, request, tour_id):
        tour = team_tours.get_team_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        return create_response(
            "success",
            "Team tour.",
            team_tours.team_tour_detail(request.user, tour, request.build_absolute_uri),
        )


class TeamTourActionView(_ReviewerView):
    """POST /api/v1/tour/team/<id>/action/ {status, remark}"""

    def post(self, request, tour_id):
        tour = team_tours.get_team_tour(request.user, tour_id)
        if tour is None:
            return _error(_NOT_FOUND, status.HTTP_404_NOT_FOUND)
        error = team_tours.act(
            request.user,
            tour,
            (request.data.get("status") or "").strip(),
            request.data.get("remark"),
        )
        if error:
            return _error({"__all__": [error]})
        return create_response(
            "success",
            "Tour updated.",
            team_tours.team_tour_detail(request.user, tour, request.build_absolute_uri),
        )
