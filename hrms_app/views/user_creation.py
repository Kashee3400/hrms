from formtools.wizard.views import SessionWizardView
from django.core.files.storage import FileSystemStorage
from hrms_app.utility.common_imports import *
from django.utils.translation import gettext_lazy as _


FORMS = [
    ("user", CustomUserForm),
    ("personal-details", PersonalDetailsForm),
    ("corresponding-address", CorrespondingAddressForm),
    ("permanent-address", PermanentAddressForm),
]

TEMPLATES = {
    "user": "hrms_app/wizard/user_form.html",
    "personal-details": "hrms_app/wizard/personal_details_form.html",
    "corresponding-address": "hrms_app/wizard/caddress_form.html",
    "permanent-address": "hrms_app/wizard/paddress_form.html",
}
class UserCreationWizard(LoginRequiredMixin, SessionWizardView):
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    template_name = "hrms_app/form_wizard.html"
    url_name = reverse_lazy("/")
    message = "Employee created successfully."

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_user_instance(self):
        """
        Get the user being edited, either from URL or created earlier in the wizard.
        """
        user_id = self.kwargs.get("pk") or self.storage.extra_data.get("created_user_id")
        return get_object_or_404(CustomUser, pk=user_id) if user_id else None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["urls"] = [
            ("dashboard", {"label": "Dashboard"}),
            ("create_user", {"label": "Create Employee"}),
        ]
        context["employee_obj"] = self.get_user_instance()
        return context

    def get_form_instance(self, step):
        """
        Provide model instance to each form step, linked to the user if applicable.
        """
        user = self.get_user_instance()
        if user:
            model_class = self.form_list[step]._meta.model
            if model_class == CustomUser:
                return user 
            return model_class.objects.filter(user=user).first()
        return None

    def post(self, *args, **kwargs):
        current_step = self.steps.current
        user = self.get_user_instance()

        if "wizard_goto_step" in self.request.POST:
            return self.render_goto_step(self.request.POST["wizard_goto_step"])
        form = self.get_form(current_step, data=self.request.POST, files=self.request.FILES)
        if form.is_valid():
            saved_instance = form.save(commit=False)
            if isinstance(saved_instance, CustomUser) and not user:
                saved_instance.set_password("12345@Kmpcl")
                saved_instance.save()
                self.storage.extra_data["created_user_id"] = saved_instance.id
            else:
                user_id = self.storage.extra_data.get("created_user_id")
                if user_id:
                    saved_instance.user_id = user_id
                saved_instance.save()
            self.storage.set_step_data(current_step, self.process_step(form))
            self.storage.set_step_files(current_step, self.process_step_files(form))
            if self.steps.current == self.steps.last:
                return self.done(self.get_form_list())
            return self.render_next_step(form)

        return self.render(form)

    def done(self, form_list, **kwargs):
        messages.success(self.request, self.message)
        return redirect("employees")

    def render_error_page(self):
        return redirect("error_page")


def cancel_user_creation(request):
    request.session.pop("current_step", None)
    return redirect("/")

def get_corresponding_address(request, user_id):
    """Fetch the corresponding address for a given user."""
    user = get_object_or_404(CustomUser, pk=user_id)
    corres_address = CorrespondingAddress.objects.filter(user=user).first()
    
    if corres_address:
        data = {
            "address_line_1": corres_address.address_line_1,
            "address_line_2": corres_address.address_line_2,
            "country": corres_address.country,
            "district": corres_address.district,
            "state": corres_address.state,
            "zipcode": corres_address.zipcode,
        }
        return JsonResponse(data)
    return JsonResponse({"error": "No corresponding address found"}, status=404)
