import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from .models import UserTour,LeaveApplication

class UserTourTable(tables.Table):
    # Specify the columns you want to display in the table
    applied_by = tables.Column()
    status = tables.Column()
    start_date = tables.DateColumn(format="Y-m-d")
    end_date = tables.DateColumn(format="Y-m-d")
    
    # Adding a custom column for 'view detail' link
    view_detail = tables.Column(empty_values=(), verbose_name="View Detail")

    # Method to generate the URL for each tour's detail page
    def render_view_detail(self, record):
        # Create the URL for the 'tour_application_detail' view
        url = reverse('tour_application_detail', args=[record.slug])
        return format_html('<a href="{}" class="button primary">View Details</a>', url)

    class Meta:
        model = UserTour
        fields = ['applied_by', 'status', 'from_destination', 'to_destination', 'start_date', 'start_time', 'end_date', 'end_time']
        attrs = {"class": "table table-striped"}




class LeaveApplicationTable(tables.Table):
    view_detail = tables.Column(empty_values=(), verbose_name="View Details")

    def render_view_detail(self, record):
        url = reverse("leave_application_detail", args=[record.slug])
        return format_html('<a href="{}" class="button primary">View Details</a>', url)

    class Meta:
        model = LeaveApplication
        # Specify no fields initially; fields will be dynamically added.
        fields = []
        attrs = {"class": "table table-striped"}