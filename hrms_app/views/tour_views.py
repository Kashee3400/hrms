from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from ..models import UserTour,TourStatusLog,LockStatus
from ..hrms.form import TourForm,BillForm,Logo
from ..forms.tour_form import (
    EmployeeTourStatusUpdateForm,
    ManagerTourStatusUpdateForm,
    AdminTourStatusUpdateForm,
)
from django.conf import settings
from django.http import HttpResponse,HttpResponseRedirect
from weasyprint import HTML
from django.template.loader import render_to_string
from hrms_app.views.mixins import ModelPermissionRequiredMixin
from hrms_app.table_classes import (
    UserTourTable,
)
import logging
from django.utils.http import urlencode
from hrms_app.tasks import send_tour_notifications
from django.contrib import messages
from django.views.generic import (
    FormView,
    DetailView,
    CreateView,
    UpdateView,
    )
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.sites.models import Site
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.views import View
from django.utils.timezone import now
from hrms_app.hrms.form import FilterForm
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

class TourPermissionMixin(LoginRequiredMixin):
    """Mixin to handle tour-related permissions"""
    
    def get_tour_application(self, slug):
        """Get tour application and check permissions"""
        tour = get_object_or_404(UserTour, slug=slug)
        user = self.request.user
        
        # Check if user has permission to view this tour
        if not self._has_view_permission(user, tour):
            raise PermissionDenied(
                _("You don't have permission to view this tour.")
            )
        
        return tour
    
    def _has_view_permission(self, user, tour):
        """Check if user can view this tour"""
        return (
            tour.applied_by == user
            or user.is_superuser
            or user.is_staff
            or (hasattr(user, 'personal_detail') and 
                user.personal_detail.designation.department.department == "admin")
            or tour.applied_by.reports_to == user
        )
    
    def _is_manager(self, user, tour):
        """Check if user is manager of the tour applicant"""
        return (
            tour.applied_by.reports_to == user
            and not user.is_superuser
            and not user.is_staff
        )
    
    def _is_admin(self, user):
        """Check if user is admin"""
        return (
            user.is_superuser
            or user.is_staff
            or (hasattr(user, 'personal_detail') and 
                user.personal_detail.designation.department.department == "admin")
        )

    def _is_employee(self, user, tour):
        """Check if user is the tour applicant"""
        return tour.applied_by == user


class TourTrackerView(ModelPermissionRequiredMixin, SingleTableMixin, FilterView):
    template_name = "hrms_app/tour-tracker.html"
    model = UserTour
    table_class = UserTourTable
    permission_action = "view"

    def get_queryset(self):
        """Filter tours based on the logged-in user’s tours and search criteria."""
        user = self.request.user
        queryset = UserTour.objects.filter(applied_by=user).order_by("-start_date")
        return queryset
        # return self.filter_tours(queryset=queryset, form=None)

    def filter_tours(self, queryset, form):
        """Apply filtering based on status and date range."""
        if form is not None and form.is_valid():
            status = form.cleaned_data.get("status", settings.PENDING)
            from_date = form.cleaned_data.get("from_date")
            to_date = form.cleaned_data.get("to_date")
            if status == "":
                status = settings.PENDING
            queryset = queryset.filter(status=status)
            if from_date:
                queryset = queryset.filter(start_date__gte=from_date)
            if to_date:
                queryset = queryset.filter(end_date__lte=to_date)
        search_term = self.request.GET.get("search", "").strip()
        if search_term:
            filters &= (
                Q(applied_by__username__icontains=search_term)
                | Q(applied_by__first_name__icontains=search_term)
                | Q(applied_by__last_name__icontains=search_term)
                | Q(from_destination__icontains=search_term)
                | Q(to_destination__icontains=search_term)
            )
        return queryset

    def get_context_data(self, **kwargs):
        """Prepare the context for the template."""
        context = super().get_context_data(**kwargs)
        form = FilterForm(self.request.GET)
        employee_tours = self.get_assigned_tours(form=form)
        context.update(
            {
                "current_date": now(),
                "form": form,
                "search_term": self.request.GET.get("search", ""),
                "selected_status": (
                    form.cleaned_data.get("status", settings.PENDING)
                    if form.is_valid()
                    else settings.PENDING
                ),
                "urls": [
                    ("dashboard", {"label": "Dashboard"}),
                    ("tour_tracker", {"label": "Tour Tracker"}),
                ],
            }
        )
        context["employee_tours"] = employee_tours
        return context

    def get_assigned_tours(self, form, *args, **kwargs):
        user = self.request.user
        if user.is_superuser:
            queryset = UserTour.objects.all().order_by("-start_date")
        else:
            queryset = UserTour.objects.filter(
                applied_by__in=user.employees.all()
            ).order_by("-start_date")
        return self.filter_tours(queryset=queryset, form=form)


class ApplyTourView(ModelPermissionRequiredMixin, CreateView):
    model = UserTour
    form_class = TourForm
    title = _("Apply Tour")
    template_name = "hrms_app/apply-tour.html"
    success_url = reverse_lazy("tour_tracker")
    permission_action = "add"

    def get_form_kwargs(self):
        """
        Inject the current user into the form for validation logic.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("tour_tracker", {"label": "Tour Tracker"}),
            (
                "apply_tour",
                {"label": "Tour Application"},
            ),
        ]
        context["urls"] = urls
        return context

    def form_valid(self, form):
        """
        If valid, save and notify.
        """
        messages.success(self.request, "Tour applied Successfully")
        tour = form.save(commit=False)        
        tour.applied_by = self.request.user

        tour.save()
        self.send_tour_notification(tour)
        
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def send_tour_notification(self, obj):
        current_site = Site.objects.get_current()
        protocol = "http"
        domain = current_site.domain
        try:
            send_tour_notifications.delay(obj.id, protocol, domain)
        except:
            pass


class TourApplicationUpdateView(ModelPermissionRequiredMixin, UpdateView):
    model = UserTour
    form_class = TourForm
    template_name = "hrms_app/apply-tour.html"
    permission_action = "change"

    def get_object(self, queryset=None):
        return get_object_or_404(UserTour, slug=self.kwargs.get("slug"))

    def form_valid(self, form):
        response = super().form_valid(form)
        tour_application = form.instance
        reason = form.cleaned_data.get("reason")
        action_by = self.request.user
        if tour_application.status == settings.APPROVED:
            tour_application.approve(action_by=action_by, reason=reason)
        elif tour_application.status == settings.REJECTED:
            tour_application.reject(action_by=action_by, reason=reason)
        elif tour_application.status == settings.CANCELLED:
            tour_application.cancel(action_by=action_by, reason=reason)
        elif tour_application.status == settings.COMPLETED:
            tour_application.complete(action_by=action_by, reason=reason)
        elif tour_application.status == settings.EXTENDED:
            tour_application.extend(action_by=action_by, reason=reason)
        elif tour_application.status == settings.PENDING_CANCELLATION:
            TourStatusLog.create_log(
                tour=tour_application,
                action_by=action_by,
                action="Cancellation request",
                comments=reason,
            )
        else:
            TourStatusLog.create_log(
                tour=tour_application,
                action_by=action_by,
                action="Updated",
                comments=reason,
            )
        messages.success(self.request, "Tour status updated successfully.")
        self.send_tour_notification(tour_application)
        return response

    def send_tour_notification(self, obj):
        current_site = Site.objects.get_current()
        protocol = "http"  # or 'https' if applicable
        domain = current_site.domain
        try:
            send_tour_notifications.delay(obj.id, protocol, domain)
        except:
            pass

    def form_invalid(self, form, msg=None):
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy(
            "tour_application_detail", kwargs={"slug": self.object.slug}
        )


class GenerateTourPDFView(View):
    def get(self, request, slug):
        tour_details = get_object_or_404(UserTour, slug=slug)
        logo = Logo.objects.all().first()
        context = {
            "object": tour_details,
            "logo": logo,
        }
        html_template = "pdf/tour_details_pdf.html"
        html_content = render_to_string(html_template, context, request=request)
        pdf_file = HTML(
            string=html_content, base_url=request.build_absolute_uri()
        ).write_pdf()
        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="tour_details.pdf"'
        return response


class UploadBillView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = BillForm
    template_name = "hrm_app/upload_bill.html"

    def get_success_url(self):
        return reverse_lazy("tour_detail", kwargs={"slug": self.kwargs["slug"]})

    def form_valid(self, form):
        tour = get_object_or_404(UserTour, pk=self.kwargs["pk"])
        bill = form.save(commit=False)
        bill.tour = tour
        bill.save()
        tour.bills_submitted = True
        tour.save()
        return super().form_valid(form)

    def test_func(self):
        tour = get_object_or_404(UserTour, pk=self.kwargs["pk"])
        return self.request.user == tour.applied_by


class TourApplicationDetailView(TourPermissionMixin, DetailView):
    """Display tour application details and status update form"""
    
    model = UserTour
    template_name = "hrms_app/tour_application_detail.html"
    context_object_name = "tour_application"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    
    def get_object(self, queryset=None):
        """Get the tour application with permission check"""
        return self.get_tour_application(self.kwargs.get("slug"))
    
    def get_context_data(self, **kwargs):
        """Add context data for the template"""
        context = super().get_context_data(**kwargs)
        tour = self.get_object()
        user = self.request.user
        
        # Determine user role
        is_manager = self._is_manager(user, tour)
        is_admin = self._is_admin(user)
        is_employee = self._is_employee(user, tour)
        
        # Get appropriate form based on role
        form = self.get_status_form(user, tour)
        context['form'] = form
        
        # URL context
        context['is_manager'] = is_manager
        context['is_admin'] = is_admin
        context['is_employee'] = is_employee
        context['is_locked'] = self.get_lock_status(tour)
        
        # Action URLs
        context['delete_url'] = self.get_delete_url(tour)
        context['edit_url'] = self.get_edit_url(tour) if is_employee else None
        context['pdf_url'] = self.get_pdf_url(tour)
        
        # Breadcrumb URLs
        context['urls'] = [
            ("dashboard", {"label": _("Dashboard")}),
            ("tour_tracker", {"label": _("Tour Tracker")}),
            (
                "tour_application_detail",
                {"label": tour.slug, "slug": tour.slug},
            ),
        ]
        
        return context
    
    def get_status_form(self, user, tour):
        """Get the appropriate form based on user role"""
        if self._is_admin(user):
            return AdminTourStatusUpdateForm(instance=tour)
        elif self._is_manager(user, tour):
            return ManagerTourStatusUpdateForm(instance=tour)
        elif self._is_employee(user, tour):
            return EmployeeTourStatusUpdateForm(instance=tour)
        else:
            raise PermissionDenied(_("You don't have permission to update this tour."))
    
    def get_delete_url(self, tour):
        """Get delete URL with next parameter"""
        delete_url = reverse(
            "generic_delete",
            kwargs={"model_name": self.model.__name__, "pk": tour.pk},
        )
        return delete_url + "?" + urlencode({"next": reverse("tour_tracker")})
    
    def get_edit_url(self, tour):
        """Get edit URL with next parameter"""
        if tour.is_editable:
            edit_url = reverse(
                "tour_application_update",
                kwargs={"slug": tour.slug},
            )
            return edit_url + "?" + urlencode(
                {"next": self.request.get_full_path()}
            )
        return None
    
    def get_pdf_url(self, tour):
        """Get PDF generation URL"""
        return reverse("generate_tour_pdf", kwargs={"slug": tour.slug})
    
    def get_lock_status(self, tour):
        """Check if tour dates are locked"""
        try:
            return LockStatus.objects.filter(
                from_date__lte=tour.start_date,
                to_date__gte=tour.start_date,
                is_locked='locked'
            ).exists()
        except Exception as e:
            # Log the error and return False
            print(f"Error checking lock status: {str(e)}")
            return False
    
    def post(self, request, *args, **kwargs):
        """Handle form submission for status updates"""
        self.object = self.get_object()
        tour = self.get_object()
        user = request.user
        
        # Get appropriate form
        form = self.get_status_form(user, tour)
        
        if request.method == 'POST':
            form = self.get_status_form_class(user, tour)(
                request.POST, instance=tour
            )
            
            if form.is_valid():
                return self.form_valid(form, tour, user)
            else:
                return self.form_invalid(form)
        
        return self.get(request, *args, **kwargs)
    
    def get_status_form_class(self, user, tour):
        """Get the form class based on user role"""
        if self._is_admin(user):
            return AdminTourStatusUpdateForm
        elif self._is_manager(user, tour):
            return ManagerTourStatusUpdateForm
        elif self._is_employee(user, tour):
            return EmployeeTourStatusUpdateForm
        else:
            raise PermissionDenied(_("You don't have permission to update this tour."))
    
    def form_valid(self, form, tour, user):
        """Handle valid form submission"""
        try:
            with transaction.atomic():
                old_status = tour.status
                updated_tour = form.save(commit=False)
                
                # Perform status-specific actions
                self.handle_status_change(
                    tour=updated_tour,
                    old_status=old_status,
                    action_by=user,
                    reason=form.cleaned_data.get("reason", "")
                )
                
                updated_tour.full_clean()
                updated_tour.save()
                
                # Create log entry
                TourStatusLog.create_log(
                    tour=updated_tour,
                    action_by=user,
                    action=updated_tour.get_status_display(),
                    comments=form.cleaned_data.get("reason", "")
                )
                
                messages.success(
                    self.request,
                    self.get_success_message(updated_tour, user)
                )
                
                return HttpResponseRedirect(self.get_success_url())
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, _("An error occurred: ") + str(e))
            return self.form_invalid(form)
    
    def handle_status_change(self, tour, old_status, action_by, reason):
        """Handle specific status transitions"""
        new_status = tour.status
        
        # Call appropriate status method
        if new_status == 'approved':
            tour.approve(action_by=action_by, reason=reason)
        elif new_status == 'rejected':
            tour.reject(action_by=action_by, reason=reason)
        elif new_status == 'cancelled':
            tour.cancel(action_by=action_by, reason=reason)
        elif new_status == 'extended':
            tour.extend(action_by=action_by, reason=reason)
        elif new_status == 'completed':
            tour.complete(action_by=action_by, reason=reason)
    
    def get_success_message(self, tour, user):
        """Get appropriate success message based on action"""
        if self._is_employee(user, tour):
            if tour.status == 'extended':
                return _("Extension request submitted successfully.")
            elif tour.status == 'pending_cancellation':
                return _("Cancellation request submitted successfully.")
        else:
            return _(f"Tour status updated to {tour.get_status_display()}.")
    
    def form_invalid(self, form):
        """Handle form errors"""
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    messages.error(self.request, f"{field}: {error}")
        
        return self.render_to_response(self.get_context_data(form=form))
    
    def get_success_url(self):
        """Redirect to tour detail page"""
        tour = self.get_object()
        return reverse_lazy(
            "tour_application_detail",
            kwargs={"slug": tour.slug}
        )
