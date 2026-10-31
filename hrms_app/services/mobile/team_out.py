"""
Who else from the reviewer's team is out on the days of a request, so they can
weigh it before deciding. Only the reviewer's own direct reportees are shown,
so someone reviewing another manager's reportee gets nothing.
"""
from django.db.models import Q
from django.utils import timezone

from hrms_app.models import LeaveApplication, UserTour
from hrms_app.services.attendance_gaps import LIVE_LEAVE_STATUSES, LIVE_TOUR_STATUSES
from hrms_app.services.mobile.formatters import employee_code_label, iso_date
from hrms_app.services.mobile.team_attendance import reportees


def _person(user, label, start, end, status):
    return {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        "code": employee_code_label(user.username),
        "label": label,
        "start": iso_date(start),
        "end": iso_date(end),
        "status": status,
    }


def team_out(reviewer, applicant, start, end):
    """Who is out in [start, end], or None if the applicant isn't a direct reportee."""
    team = list(reportees(reviewer))
    if applicant.pk not in {member.pk for member in team}:
        return None
    others = [member for member in team if member.pk != applicant.pk]

    leaves = LeaveApplication.objects.filter(
        appliedBy__in=others,
        status__in=LIVE_LEAVE_STATUSES,
        startDate__date__lte=end,
        endDate__date__gte=start,
    ).select_related("appliedBy", "leave_type")
    tours = (
        UserTour.objects.filter(applied_by__in=others, status__in=LIVE_TOUR_STATUSES, start_date__lte=end)
        .filter(Q(end_date__gte=start) | Q(extended_end_date__gte=start))
        .select_related("applied_by")
    )

    people = [
        _person(
            leave.appliedBy,
            leave.leave_type.leave_type_short_code,
            timezone.localtime(leave.startDate).date(),
            timezone.localtime(leave.endDate).date(),
            leave.status,
        )
        for leave in leaves
    ] + [
        _person(tour.applied_by, "Tour", tour.start_date, tour.extended_end_date or tour.end_date, tour.status)
        for tour in tours
    ]
    return {"team_size": len(others), "people": sorted(people, key=lambda p: (p["start"], p["name"]))}
