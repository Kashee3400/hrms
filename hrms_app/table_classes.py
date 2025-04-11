import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from .models import UserTour, LeaveApplication
from .models import AttendanceLog


class UserTourTable(tables.Table):
    applied_by = tables.Column()
    status = tables.Column()
    start_date = tables.DateColumn(format="F j, Y")
    end_date = tables.DateColumn(format="F j, Y")

    view_detail = tables.Column(empty_values=(), verbose_name="Action")

    # Method to generate the URL for each tour's detail page
    def render_view_detail(self, record):
        # Create the URL for the 'tour_application_detail' view
        url = reverse("tour_application_detail", args=[record.slug])
        return format_html('<a href="{}" class="button primary">Details/Edit/Delete/Cancel</a>', url)

    class Meta:
        model = UserTour
        fields = [
            "applied_by",
            "status",
            "from_destination",
            "to_destination",
            "start_date",
            "end_date",
        ]
        attrs = {"class": "table table-striped"}


class LeaveApplicationTable(tables.Table):
    startDate = tables.DateColumn(format="F j, Y")
    endDate = tables.DateColumn(format="F j, Y")
    usedLeave = tables.Column(verbose_name="Total Days")
    view_detail = tables.Column(empty_values=(), verbose_name="Action")
    def render_view_detail(self, record):
        url = reverse("leave_application_detail", args=[record.slug])
        return format_html('<a href="{}" class="button primary">Details/Cancel/Edit/Delete</a>', url)

    class Meta:
        model = LeaveApplication
        fields = ["appliedBy","leave_type","startDate","endDate","usedLeave","status"]
        attrs = {"class": "table table-striped"}


class AttendanceLogTable(tables.Table):
    from_date = tables.DateTimeColumn(format="d M Y, h:i A", verbose_name="From Date")
    to_date = tables.DateTimeColumn(format="d M Y, h:i A", verbose_name="To Date")
    actions = tables.Column(empty_values=(), verbose_name="Actions")

    class Meta:
        model = AttendanceLog
        template_name = "django_tables2/bootstrap.html"
        fields = (
            "applied_by",
            "reg_status",
            "status",
            "from_date",
            "to_date",
            "reg_duration",
            "is_submitted",
        )
        attrs = {"class": "table table-striped"}

    def render_actions(self, record):
        view_url = reverse("event_detail", args=[record.slug])
        return format_html(
            '<a href="{}" class="btn btn-primary btn-sm"><i class="fas fa-eye"></i> View Detail</a>',
            view_url,
        )
