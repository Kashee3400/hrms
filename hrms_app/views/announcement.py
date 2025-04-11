from hrms_app.utility.common_imports import *
from django.utils.translation import gettext_lazy as _
from hrms_app.models import HRAnnouncement

class AnnouncementView(LoginRequiredMixin, UpdateView):
    model = HRAnnouncement
    form_class = HRAnnouncementAdminForm
    template_name = "hrms_app/hr/announcement.html"
    success_url = reverse_lazy("announcements")
    context_object_name = 'object'

    def get_object(self, queryset=None):
        pk = self.kwargs.get("pk")
        if pk:
            return get_object_or_404(HRAnnouncement, pk=pk)
        return HRAnnouncement()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_date"] = now().strftime("%A, %d %B %Y")
        context["title"] = _("Edit Announcement") if self.object.pk else _("Create Announcement")
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, _("Announcement saved successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Failed to save announcement. Please check the form."))
        return super().form_invalid(form)

