from django.views.generic import CreateView, UpdateView
from ..mixins.short_leave_mixin import ShortLeaveBaseMixin
from hrms_app.models import LeaveApplication
from django.utils.translation import gettext_lazy as _

class ShortLeaveCreateView(ShortLeaveBaseMixin, CreateView):
    """
    Create Short Leave
    """
    
    title = _("Create Update Leave Application")

    pass


class ShortLeaveUpdateView(ShortLeaveBaseMixin, UpdateView):
    """
    Update Short Leave
    """
    
    title = _("Create Update Leave Application")


    def get_queryset(self):
        return LeaveApplication.objects.filter(
            user=self.request.user,
            leave_type__leave_type_short_code="STL",
        )
