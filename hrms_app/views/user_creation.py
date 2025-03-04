from formtools.wizard.views import SessionWizardView
# Standard library imports
import logging
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
)
from django.urls import reverse, reverse_lazy
from django.core.files.storage import FileSystemStorage, default_storage
from django.forms.models import model_to_dict
from django.utils.translation import gettext_lazy as _
from django.conf import settings
# Local imports
from hrms_app.hrms.form import CustomUserForm,PersonalDetailsForm,PermanentAddressForm,CorrespondingAddressForm,CorrespondingAddress
from django.contrib.auth import get_user_model
CustomUser = get_user_model()
logger = logging.getLogger(__name__)
from django.http import JsonResponse


FORMS = [
    ("user", CustomUserForm),
    ("personal", PersonalDetailsForm),
    ("caddress", CorrespondingAddressForm),
    ("paddress", PermanentAddressForm),
]

TEMPLATES = {
    "user": "hrms_app/wizard/user_form.html",
    "personal": "hrms_app/wizard/personal_details_form.html",
    "caddress": "hrms_app/wizard/caddress_form.html",
    "paddress": "hrms_app/wizard/paddress_form.html",
}

class UserCreationWizard(LoginRequiredMixin, SessionWizardView):
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    template_name = "hrms_app/form_wizard.html"
    url_name = reverse_lazy("/")

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_user_instance(self):
        """Retrieve the user instance if it exists."""
        user_id = self.kwargs.get("pk")
        return get_object_or_404(CustomUser, pk=user_id) if user_id else None

    def get_context_data(self, **kwargs):
        """Provide additional context to the template."""
        
        context = super().get_context_data(**kwargs)
        context["urls"] = [
            ("dashboard", {"label": "Dashboard"}),
            ("create_user", {"label": "Create Employee"}),
        ]
        context.update({
            "employee_obj":self.get_user_instance()
        })
        return context

    def get_form_instance(self, step):
        """Ensure the form is linked with the existing user instance."""
        user = self.get_user_instance()
        if user:
            model_class = self.form_list[step]._meta.model
            if model_class == CustomUser:
                return user  # Link directly to user instance
            
            return model_class.objects.filter(user=user).first() or None
        return None

    def post(self, *args, **kwargs):
        """Handle form submission and save data immediately."""
        current_step = self.steps.current
        user = self.get_user_instance()

        if "wizard_goto_step" in self.request.POST:
            return self.render_goto_step(self.request.POST["wizard_goto_step"])

        form = self.get_form(current_step, data=self.request.POST, files=self.request.FILES)

        if form.is_valid():
            saved_instance = form.save(commit=False)
            # If creating a user, set a default password
            if isinstance(saved_instance, CustomUser) and not user:
                saved_instance.set_password("12345@Kmpcl")
            # Ensure user linkage
            if not isinstance(saved_instance, CustomUser):
                saved_instance.user = user
            saved_instance.save()  # Save to database
            return super().post(*args, **kwargs)  # Move to next step
        return self.render(form)

    def render_error_page(self):
        """Redirect to an error page in case of failure."""
        return redirect("error_page")

    def done(self, form_list, **kwargs):
        """Redirect after all steps are completed."""
        return redirect("employees")


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
