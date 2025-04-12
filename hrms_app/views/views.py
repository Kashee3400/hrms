from hrms_app.utility.common_imports import *
from django.utils.translation import gettext_lazy as _


def custom_permission_denied(request, exception=None):
    error_message = (
        str(exception)
        if exception
        else "You do not have permission to access this page."
    )
    return render(request, "403.html", {"error_message": error_message})


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "admin/index.html"
    title = _("Dashboard")

    def dispatch(self, request, *args, **kwargs):
        # Check if the user is a superuser
        if not (request.user.is_superuser or request.user.is_staff):
            return HttpResponseForbidden(
                "You do not have permission to access this page."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_employee_wishing(self):
        today = now().date()
        employees = PersonalDetails.objects.filter(
            models.Q(birthday__month=today.month, birthday__day=today.day)
            | models.Q(marriage_ann__month=today.month, marriage_ann__day=today.day)
            | models.Q(doj__month=today.month, doj__day=today.day)
        )

        light_colors = [
            "bg-light-blue",
            "bg-light-pink",
            "bg-light-yellow",
            "bg-light-green",
            "bg-light-coral",
            "bg-light-cyan",
            "bg-light-lavender",
        ]

        for employee in employees:
            events = []
            if (
                employee.birthday
                and employee.birthday.month == today.month
                and employee.birthday.day == today.day
            ):
                events.append("🎉 Happy Birthday! 🎉")
            if (
                employee.marriage_ann
                and employee.marriage_ann.month == today.month
                and employee.marriage_ann.day == today.day
            ):
                events.append("💍 Happy Marriage Anniversary! 💍")
            if (
                employee.doj
                and employee.doj.month == today.month
                and employee.doj.day == today.day
            ):
                events.append("🎊 Happy Job Anniversary! 🎊")
            employee.events = events

            # Assign a random light color to each employee
            employee.bg_color = random.choice(light_colors)

        return employees

    def get_context_data(self, **kwargs):
        """Add custom context data for the dashboard."""
        context = super().get_context_data(**kwargs)
        context["current_date"] = datetime.now()
        users = User.objects.all()
        context["users"] = users
        urls = [
            ("dashboard", {"label": "Dashboard"}),
        ]
        context["urls"] = urls
        context["form"] = PopulateAttendanceForm()
        context.update(
            {
                "title": self.title,
                "employees": self.get_employee_wishing(),
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST requests."""
        return super().post(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "hrms_app/home.html"
    title = _("Home")

    def get_context_data(self, **kwargs):
        """Add custom context data for the dashboard."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["current_date"] = datetime.now().strftime("%A, %d %B %Y")
        check_in_time, check_out_time = at.get_check_in_out_times(user)
        context["check_in_time"] = self.format_time(check_in_time)
        context["check_out_time"] = self.format_time(check_out_time)
        context["total_hours"] = self.calculate_total_hours(
            check_in_time, check_out_time
        )
        from_datetime, to_datetime = at.get_from_to_datetime()
        context["days_in_month"] = at.get_days_in_month(from_datetime, to_datetime)
        employees = user.employees.all() | User.objects.filter(id=user.id)
        count_list = self.get_counts_as_list(user.employees.all())
        context["attendance_data"] = self.get_attendance(
            employees, from_datetime, to_datetime
        )
        context["employees"] = employees
        context["title"] = self.title
        context["from_datetime"] = from_datetime
        context["to_datetime"] = to_datetime
        context["count_list"] = count_list
        return context

    def format_time(self, time_obj):
        """Format time as HH:MM AM/PM or return '--:--' if None."""
        return time_obj.strftime("%I:%M %p") if time_obj else "--:--"

    def get_counts_as_list(self, employees):
        user = self.request.user
        if user.is_superuser:
            employee_ids = None
        else:
            employee_ids = list(employees.values_list("id", flat=True))
        filter_kwargs = {} if user.is_superuser else {"applied_by_id__in": employee_ids}
        leave_filter_kwargs = (
            {} if user.is_superuser else {"appliedBy_id__in": employee_ids}
        )
        counts = {
            "regularization": AttendanceLog.objects.filter(
                is_regularisation=True,
                is_submitted=True,
                status=settings.PENDING,
                **filter_kwargs,
            ).count(),
            "leave": LeaveApplication.objects.filter(
                status=settings.PENDING, **leave_filter_kwargs
            ).count(),
            "tour": UserTour.objects.filter(
                status=settings.PENDING, **filter_kwargs
            ).count(),
        }

        items = [
            {
                "key": "leave",
                "title": _("Leaves"),
                "icon": "fas fa-hourglass-half",
                "link": reverse("leave_tracker"),
            },
            {
                "key": "tour",
                "title": _("Tours"),
                "icon": "fas fa-plane-departure",
                "link": reverse("tour_tracker"),
            },
            {
                "key": "regularization",
                "title": _("Regularizations"),
                "icon": "fas fa-check-circle",
                "link": reverse("regularization"),
            },
        ]

        return [
            {
                "count": counts[item["key"]],
                "title": item["title"],
                "icon": item["icon"],
                "link": self.request.build_absolute_uri(item["link"]),
            }
            for item in items
        ]

    def calculate_total_hours(self, check_in, check_out):
        """Calculate total working hours and minutes."""
        if not check_in or not check_out:
            return "00h : 00m"

        total_duration = check_out - check_in
        hours, remainder = divmod(total_duration.total_seconds(), 3600)
        minutes = remainder // 60
        return f"{int(hours):02}h : {int(minutes):02}m"

    def get_attendance(self, employees, from_datetime, to_datetime):
        """Fetch attendance logs and process attendance data."""
        employee_ids = list(employees.values_list("id", flat=True))

        # Fetch attendance-related logs
        attendance_logs = at.get_attendance_logs(
            employee_ids, from_datetime, to_datetime
        )
        leave_logs = at.get_leave_logs(employee_ids, from_datetime, to_datetime)
        tour_logs = at.get_tour_logs(employee_ids, from_datetime, to_datetime)
        holidays = at.get_holiday_logs(from_datetime, to_datetime)

        # Map attendance data
        return at.map_attendance_data(
            attendance_logs=attendance_logs,
            leave_logs=leave_logs,
            holidays=holidays,
            tour_logs=tour_logs,
            start_date_object=from_datetime,
            end_date_object=to_datetime,
        )


class EmployeeProfileView(LoginRequiredMixin, DetailView):
    template_name = "hrms_app/profile.html"
    model = CustomUser
    context_object_name = "employee"
    permission_action = "change"
    success_message = ""
    error_message = ""

    def get_object(self, queryset=None):
        user_id = self.kwargs.get("pk")
        if user_id:
            return get_object_or_404(CustomUser, id=user_id)
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.get_object()
        urls = [
            ("home", {"label": "Home"}),
        ]
        context.update(
            {
                "profile_ob": employee,
                "cform": CorrespondingAddressForm(
                    instance=employee.corres_addresses.last()
                ),
                "pform": PermanentAddressForm(
                    instance=employee.permanent_addresses.last()
                ),
                "avatar_form": AvatarUpdateForm(),
                "cform_name": "cform_submit",
                "pform_name": "pform_submit",
                "cform_button_text": "Update Corresponding Address",
                "button_text": "Update Address",
                "urls": urls,
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        employee = self.get_object()
        if "form_submit" in request.POST:
            form_type = request.POST.get("form_submit")
            if form_type == "cform":
                form = CorrespondingAddressForm(
                    request.POST, instance=employee.corres_addresses.last()
                )
                success_message = "Corresponding address updated successfully."
                error_message = "Error updating corresponding address."

            elif form_type == "pform":
                form = PermanentAddressForm(
                    request.POST, instance=employee.permanent_addresses.last()
                )
                success_message = "Permanent address updated successfully."
                error_message = "Error updating permanent address."

            elif form_type == "avatar_form":
                form = AvatarUpdateForm(
                    request.POST, request.FILES, instance=employee.personal_detail
                )
                success_message = "Avatar updated successfully."
                error_message = "Error updating avatar."
            else:
                form = None
            if form:
                if form.is_valid():
                    form.save()
                    messages.success(request, success_message)
                else:
                    messages.error(request, error_message)

        return redirect(request.path)

from django.urls import reverse

class PersonalDetailUpdateView(ModelPermissionRequiredMixin, UpdateView):
    model = PersonalDetails
    form_class = EmployeePersonalDetailForm
    template_name = 'hrms_app/employee/personal_detail_form.html'
    permission_action = "change"

    def get_object(self, queryset=None):
        if self.request.user.is_superuser and 'pk' in self.kwargs:
            return get_object_or_404(PersonalDetails, pk=self.kwargs['pk'])
        return get_object_or_404(PersonalDetails, user=self.request.user)

    def form_valid(self, form):
        old_instance = self.get_object()
        changed_fields = {}

        for field in form.changed_data:
            old_value = getattr(old_instance, field)
            new_value = form.cleaned_data.get(field)
            if old_value != new_value:
                changed_fields[field] = (old_value, new_value)
        # Trigger Celery task
        if changed_fields:
            send_personal_detail_update_email.delay(
                user_full_name=self.request.user.get_full_name(),
                username=self.request.user.username,
                changed_fields=changed_fields,
            )

        messages.success(self.request, "Your personal details have been updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('employee_profile', kwargs={'pk': self.object.pk})


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        urls = [
            ("home", {"label": "Home"}),
        ]
        context.update(
            {                "urls": urls,
            }
        )
        return context

class LeaveTrackerView(ModelPermissionRequiredMixin, SingleTableMixin, TemplateView):
    template_name = "hrms_app/leave-tracker.html"
    model = LeaveApplication
    table_class = LeaveApplicationTable
    permission_action = "view"
    title = _("Leave Tracker")
    
    def perform_search(self, queryset, search_term):
        if search_term:
            queryset = queryset.filter(
                Q(appliedBy__username__icontains=search_term)
                | Q(
                    appliedBy__first_name__icontains=search_term
                )  # Search by first name
                | Q(appliedBy__last_name__icontains=search_term)
            )
        return queryset

    def get_assigned_employee_leaves(
        self, user, form, page=1, per_page=10, *args, **kwargs
    ):
        if user.is_superuser:
            queryset = (
                LeaveApplication.objects.all()
                .exclude(appliedBy=user)
                .order_by("-startDate")
            )
        else:
            queryset = LeaveApplication.objects.filter(
                appliedBy__in=user.employees.all()
            ).order_by("-startDate")
        queryset = self.get_filtered_leaves(queryset=queryset, form=form)
        paginator = Paginator(queryset, per_page)
        try:
            leaves = paginator.page(page)
        except PageNotAnInteger:
            leaves = paginator.page(1)
        except EmptyPage:
            leaves = paginator.page(paginator.num_pages)
        return {
            "leaves": leaves,
            "pagination": {
                "has_previous": leaves.has_previous(),
                "has_next": leaves.has_next(),
                "current_page": leaves.number,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "per_page": per_page,
            },
        }

    def get_filtered_leaves(self, queryset, form=None):
        """Apply filters to the leave applications."""
        year = timezone.now().year
        queryset = queryset.filter(startDate__date__year=year)
        if form is not None and form.is_valid():
            status = form.cleaned_data.get("status")
            from_date = form.cleaned_data.get("fromDate")
            to_date = form.cleaned_data.get("toDate")
            if status == "":
                status = settings.PENDING
            queryset = queryset.filter(status=status)
            if from_date:
                queryset = queryset.filter(startDate__gte=from_date)
            if to_date:
                queryset = queryset.filter(endDate__lte=to_date)
        search_term = self.request.GET.get("q", "").strip()
        if search_term:
            queryset = self.perform_search(queryset=queryset, search_term=search_term)
        return queryset

    def get_queryset(self):
        user = self.request.user
        user_leaves = LeaveApplication.objects.filter(appliedBy=user).order_by(
            "-startDate"
        )
        return self.get_filtered_leaves(queryset=user_leaves, form=None)

    def get_context_data(self, **kwargs):
        """Prepare the context for the template."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        form = FilterForm(self.request.GET)
        try:
            context.update(
                {
                    "current_date": now(),
                    "form": form,
                    "employee_leaves": self.get_assigned_employee_leaves(
                        user, form, page=self.request.GET.get("page", 1), per_page=12
                    ),
                    "pending_leave_count": LeaveApplication.objects.filter(
                        appliedBy=user, status=settings.PENDING
                    ).count(),
                    "title": self.title,
                    "urls": [
                        ("home", {"label": "Home"}),
                        ("leave_tracker", {"label": "Leave Tracker"}),
                    ],
                }
            )
        except Exception as e:
            logger.exception(f"Unexpected error in context preparation: {e}")
            messages.error(
                self.request,
                "An error occurred while loading the page. Please try again later.",
            )
        return context


@method_decorator(login_required, name="dispatch")
class ApplyOrUpdateLeaveView(
    LoginRequiredMixin, SuccessMessageMixin, ModelFormMixin, FormView
):
    model = LeaveApplication
    form_class = LeaveApplicationForm
    template_name = "hrms_app/apply-leave.html"
    success_message_create = _("Leave applied successfully.")
    success_message_update = _("Leave updated successfully.")
    permission_action_create = "add"
    permission_action_update = "change"
    title = _("Create Update Leave Application")

    def dispatch(self, request, *args, **kwargs):
        """Check if the user has permission dynamically for the model."""
        self.object = None
        if "slug" in kwargs:  # 'slug' determines update vs. create
            self.object = self.get_object()
            permission_action = self.permission_action_update
        else:
            permission_action = self.permission_action_create

        opts = self.model._meta
        perm = f"{opts.app_label}.{permission_action}_{opts.model_name}"
        if not request.user.has_perm(perm):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        """Retrieve the form instance with the correct data."""
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Pass additional data to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["leave_type"] = (
            self.object.leave_type.id if self.object else self.kwargs.get("leave_type")
        )

        return kwargs

    def form_valid(self, form):
        """Handle successful form submission with probation check."""
        user = self.request.user
        if hasattr(user, "personal_detail") and user.personal_detail.doj:
            doj = user.personal_detail.doj
            probation_period_end = doj + timedelta(days=180)
            leave_type = form.cleaned_data.get("leave_type")
            if (
                leave_type
                and leave_type.leave_type_short_code == "EL"
                and now().date() < probation_period_end
            ):
                messages.error(
                    self.request,
                    "You are still in the probation period and cannot apply for Earned Leave (EL).",
                )
                return self.form_invalid(form)
        leave_application = form.save(commit=False)
        stats = LeaveStatsManager(user=user, leave_type=leave_application.leave_type)
        remaining_balance = stats.get_remaining_balance(year=timezone.now().year)
        if leave_application.usedLeave > remaining_balance:
            form.add_error("usedLeave", _("Total days exceeds your remaining balance."))
            return self.form_invalid(form)
        leave_application.appliedBy = user
        leave_application.attachment = self.request.FILES.get("attachment")
        leave_application.save()
        success_message = (
            self.success_message_update if self.object else self.success_message_create
        )
        messages.success(self.request, success_message)
        next_url = self.request.POST.get("next")
        if next_url and urlparse(next_url).netloc == "":
            return redirect(next_url)

        return redirect(reverse_lazy("leave_tracker"))

    def form_invalid(self, form):
        """Handle form submission failure."""
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Prepare context data for the template."""
        context = super().get_context_data(**kwargs)
        leave_type_id = (
            self.object.leave_type.id if self.object else self.kwargs.get("leave_type")
        )
        leave_balance = LeaveBalanceOpenings.objects.filter(
            user=self.request.user,
            leave_type_id=leave_type_id,
            year=timezone.now().year,
        ).first()
        stats = LeaveStatsManager(
            user=self.request.user, leave_type=leave_balance.leave_type
        )
        el_count = stats.get_el_applied_times()
        rem_bal = stats.get_remaining_balance(year=timezone.now().year)
        context.update(
            {
                "leave_balance": leave_balance,
                "rem_bal": int(rem_bal),
                "object": self.object,
                "el_count": el_count,
                "form": kwargs.get(
                    "form",
                    LeaveApplicationForm(
                        instance=self.object,  # Ensure instance is passed
                        user=self.request.user,
                        leave_type=leave_type_id,
                    ),
                ),
                "title": self.title,
                "urls": [
                    ("home", {"label": "Home"}),
                    ("leave_tracker", {"label": "Leave Tracker"}),
                ],
            }
        )
        return context

    def get_object(self):
        """Retrieve the object for update."""
        if "slug" in self.kwargs:
            return LeaveApplication.objects.get(slug=self.kwargs["slug"])
        return None


class GenericDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    template_name = "hrms_app/confirm_delete.html"
    success_message = "Deleted successfully."
    permission_action = "delete"

    def dispatch(self, request, *args, **kwargs):
        """Check if the user has permission dynamically for the model."""
        self.model = self.get_model()
        opts = self.model._meta
        perm = f"{opts.app_label}.{self.permission_action}_{opts.model_name}"
        if not request.user.has_perm(perm):
            raise PermissionDenied("You do not have permission to delete this item.")
        return super().dispatch(request, *args, **kwargs)

    def get_model(self):
        """Get the model class based on the URL parameter."""
        model_name = self.kwargs.get("model_name")
        return apps.get_model("hrms_app", model_name)

    def get_object(self):
        """Get the object to be deleted."""
        model = self.get_model()
        return get_object_or_404(model, pk=self.kwargs.get("pk"))

    def get_success_url(self):
        """Redirect to 'next' if it's safe, else fallback."""
        next_url = self.request.GET.get("next")
        if next_url:
            parsed_url = urlparse(next_url)
            if not parsed_url.netloc or parsed_url.netloc == self.request.get_host():
                return next_url

        return reverse_lazy("home")

    def delete(self, request, *args, **kwargs):
        """Handle successful deletion."""
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, self.success_message)
        return response

    def get_context_data(self, **kwargs):
        """Prepare context data for the template."""
        context = super().get_context_data(**kwargs)
        object_to_delete = self.get_object()

        # Dynamically fetch related logs or objects
        related_objects = self.get_related_objects(object_to_delete)

        # Pass the related objects and data to the context
        context["object_name"] = self.model._meta.verbose_name
        context["related_objects"] = related_objects
        context["cancel_url"] = self.get_success_url()
        return context

    def get_related_objects(self, object_to_delete):
        """Dynamically fetch related objects."""
        related_objects = []

        for rel in object_to_delete._meta.related_objects:
            if hasattr(rel, "related_model"):  # Check if the model has a related model
                related_model = rel.related_model
                accessor_name = rel.get_accessor_name()  # Correct field accessor name

                # Fetch related objects using the accessor name
                related_data = getattr(object_to_delete, accessor_name).all()
                for related_item in related_data:
                    related_objects.append(
                        {
                            "model_name": related_model._meta.verbose_name,  # Add verbose name here
                            "item": related_item,
                        }
                    )

        return related_objects


class LeaveApplicationUpdateView(ModelPermissionRequiredMixin, UpdateView):
    model = LeaveApplication
    form_class = LeaveStatusUpdateForm
    template_name = "hrms_app/leave_application_detail.html"
    permission_action = "change"
    

    def get_object(self, queryset=None):
        return get_object_or_404(LeaveApplication, slug=self.kwargs.get("slug"))

    def update_leave_balance(self, leave_application):
        leave_balance = LeaveBalanceOpenings.objects.filter(
            user=leave_application.appliedBy,
            leave_type=leave_application.leave_type,
            year=localtime(leave_application.startDate).year,
        ).first()
        if leave_balance:
            if leave_application.status == settings.APPROVED:
                leave_balance.remaining_leave_balances -= leave_application.usedLeave
            elif leave_application.status == settings.CANCELLED:
                leave_balance.remaining_leave_balances += leave_application.usedLeave
            leave_balance.save()

    def form_valid(self, form):
        response = super().form_valid(form)
        leave_application = form.instance
        action_by = self.request.user
        self.update_leave_balance(leave_application)
        LeaveLog.create_log(leave_application, action_by, leave_application.status)
        messages.success(
            self.request,
            _(f"Leave application {leave_application.status} successfully"),
        )
        return response

    def get_success_url(self):
        return reverse_lazy(
            "leave_application_detail", kwargs={"slug": self.object.slug}
        )

class LeaveApplicationDetailView(ModelPermissionRequiredMixin, DetailView):
    model = LeaveApplication
    template_name = "hrms_app/leave_application_detail.html"
    context_object_name = "leave_application"
    permission_denied_message = _("You do not have permission to access this page.")
    permission_action = "view"
    title = _("Leave Application Detail")

    def get_object(self, queryset=None):
        leave_application = super().get_object(queryset)
        if self.has_permission_to_view(leave_application):
            return leave_application
        raise PermissionDenied(self.permission_denied_message)

    def has_permission_to_view(self, leave_application):
        user = self.request.user
        return (
            leave_application.appliedBy == user
            or user.is_superuser
            or user.is_staff
            or leave_application.appliedBy.reports_to == user
            or user.personal_detail.designation.department.department == "admin"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leave_application = self.get_object()
        context["is_locked"] = self.get_lock_status(leave_application=leave_application)
        context.update(
            {
                "is_manager": self.is_manager(leave_application),
                "status_form": self.get_status_form(),
                "leave_balance": self.get_leave_type_balance(leave_application),
                "delete_url": self.get_delete_url(),
                "edit_url": self.get_edit_url(),
                "urls": self.get_breadcrumb_urls(leave_application),
                "title": self.title,
            }
        )
        return context

    def is_manager(self, leave_application):
        return self.request.user == leave_application.appliedBy.reports_to

    def get_lock_status(self, leave_application):
        lock_status = LockStatus.objects.filter(
            from_date__lte=localtime(
                leave_application.startDate
            ).date(),  # 21 feb 2025    15 mar 2025
            to_date__gte=localtime(
                leave_application.startDate
            ).date(),  # 20 mar 2025     15 Mar 2025
        )
        return lock_status.exists()

    def get_status_form(self):
        return LeaveStatusUpdateForm(user=self.request.user, instance=self.object)

    def get_leave_type_balance(self, leave_application):
        return LeaveBalanceOpenings.objects.filter(
            user=leave_application.appliedBy,
            year=localtime(leave_application.startDate).date().year,
            leave_type=leave_application.leave_type,
        ).first()

    def get_delete_url(self):
        return (
            reverse(
                "generic_delete",
                kwargs={"model_name": self.model.__name__, "pk": self.object.pk},
            )
            + f"?next={reverse_lazy('leave_tracker')}"
        )

    def get_edit_url(self):
        return reverse("update_leave", kwargs={"slug": self.object.slug})

    def get_breadcrumb_urls(self, leave_application):
        return [
            ("home", {"label": "Home"}),
            ("leave_tracker", {"label": "Leave Tracker"}),
            (
                "leave_application_detail",
                {
                    "label": f"{leave_application.applicationNo}",
                    "slug": leave_application.slug,
                },
            ),
        ]


class LeaveApplicationListView(View, LeaveListViewMixin):
    START_LEAVE_TYPE_CHOICES = {
        "1": "Full Day",
        "2": "First Half (Morning)",
        "3": "Second Half (Afternoon)",
    }

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "User not authenticated"}, status=401)

        leave_applications = [
            {
                "name": f"{leaveApplication.appliedBy.first_name} {leaveApplication.appliedBy.last_name}",
                "applicationNo": leaveApplication.applicationNo,
                "leave_type": leaveApplication.leave_type.leave_type,
                "startDate": format_date(leaveApplication.startDate),
                "startDayChoice": self.START_LEAVE_TYPE_CHOICES.get(
                    leaveApplication.startDayChoice, leaveApplication.startDayChoice
                ),
                "endDate": format_date(leaveApplication.endDate),
                "endDayChoice": self.START_LEAVE_TYPE_CHOICES.get(
                    leaveApplication.endDayChoice, leaveApplication.endDayChoice
                ),
                "usedLeave": leaveApplication.usedLeave,
                "status": leaveApplication.status.capitalize(),
            }
            for leaveApplication in request.user.leaves.all()
        ]

        data = {
            "header": self.get_headers(),  # Assuming get_headers() is still applicable
            "data": leave_applications,
        }

        return JsonResponse(data)


class EventPageView(ModelPermissionRequiredMixin, TemplateView):
    template_name = "hrms_app/calendar.html"
    model = AttendanceLog
    title = _("Attendance Log")
    permission_action = "view"
    

    def get_context_data(self, **kwargs):
        """Prepare the context for the template."""
        context = super().get_context_data(**kwargs)
        initial_data = {"employee": self.request.user}
        form = EmployeeChoicesForm(self.request.GET or initial_data)

        if form.is_valid():
            employee = form.cleaned_data.get("employee")
        else:
            employee = self.request.user

        employee = self.request.user if employee is None else employee

        context.update(
            {
                "current_date": now(),
                "form": form,
                "employee": employee,
                "title": self.title,
                "urls": [
                    ("dashboard", {"label": "Dashboard"}),
                    ("calendar", {"label": "Attendance Calendar"}),
                ],
            }
        )
        return context



class EventDetailPageView(ModelPermissionRequiredMixin,UpdateView):
    model = AttendanceLog
    template_name = "hrms_app/event_detail.html"
    form_class = AttendanceLogForm
    slug_field = "slug"
    slug_url_kwarg = "slug"
    title = _("Attendance Log")
    permission_action = "change"
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user

        if self._can_user_access_log(user, obj):
            return obj
        raise PermissionDenied()

    def _can_user_access_log(self, user, log):
        return (
            log.applied_by == user or
            log.applied_by.reports_to == user or
            user.is_staff or
            user.is_superuser or
            getattr(user.personal_detail.designation.department, 'department', None) == "admin"
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        log = self.get_object()
        early_going, late_coming = self.check_event(log)
        
        kwargs.update({
            "user": self.request.user,
            "is_manager": self.request.user == log.applied_by.reports_to,
            "early_going":early_going,
            "late_coming":late_coming,
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = self.get_object()
        early_going, late_coming = self.check_event(log)
        context.update({
            "is_manager": self.request.user == log.applied_by.reports_to,
            "urls": self._get_breadcrumb_urls(log),
            "action_form": AttendanceLogActionForm(),
            "title": self.title,
            "subtitle": log.slug,
            "early_going":early_going,
            "late_coming":late_coming,
            "reg_count": self._get_regularization_count(log),
        })
        return context

    def form_valid(self, form):
        if self._is_beyond_policy_allowed() or not self._has_exceeded_regularization_limit():
            return self._process_submission(form)
        messages.error(
            self.request,
            _(f"You have already applied for the maximum number of regularizations ({self._get_regularization_limit()} times).")
        )
        return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("There were errors in your submission. Please correct them and try again."))
        return self.render_to_response(self.get_context_data(form=form))

    def _get_app_setting(self, key, default=None):
        setting = AppSetting.objects.filter(key=key).first()
        return setting if setting else default

    def _get_regularization_limit(self):
        setting = self._get_app_setting("REGULARIZATION_LIMIT")
        return int(getattr(setting, 'value', 3))

    def _is_beyond_policy_allowed(self):
        setting = self._get_app_setting("REGULARIZATION_LIMIT")
        return getattr(setting, 'beyond_policy', False)

    def _has_exceeded_regularization_limit(self):
        current_log = self.get_object()
        return self._get_regularization_count(current_log) >= self._get_regularization_limit()

    def _get_regularization_count(self, log):
        return AttendanceLog.objects.filter(
            applied_by=log.applied_by,
            start_date__year=log.start_date.year,
            start_date__month=log.start_date.month,
        ).filter(Q(regularized=True) | Q(is_submitted=True)).count()

    def _get_breadcrumb_urls(self, log):
        return [
            ("dashboard", {"label": "Dashboard"}),
            ("calendar", {"label": "Attendance"}),
            ("event_detail", {"label": log.title, "slug": log.slug}),
        ]
    def check_event(self, obj):
        """
        This function checks the events (Early Going and Late Coming)
        based on the user check-in and check-out time.
        """
        late_coming_case = {}
        early_going_case = {}
        
        user = obj.applied_by
        user_shift = user.shifts.last().shift_timing
        
        if not obj.regularized:
            check_in_datetime = localtime(obj.start_date)
            check_out_datetime = localtime(obj.end_date)
            grace_start_time = user_shift.grace_start_time
            grace_end_time = user_shift.grace_end_time
            grace_start_datetime = make_aware(datetime.combine(check_in_datetime.date(), grace_start_time))
            grace_end_datetime = make_aware(datetime.combine(check_out_datetime.date(), grace_end_time))
            check_in_plus_8hrs = check_in_datetime + timedelta(hours=8)
            
            if check_in_datetime > grace_start_datetime:
                duration_td = check_in_datetime - grace_start_datetime
                duration_str = str(duration_td)[:-3]  # Format: 'HH:MM'
                late_coming_case = {
                    "case": "late_coming",
                    "from_date": grace_start_datetime,
                    "to_date": check_in_datetime,
                    "duration": duration_str
                }
            
            if check_out_datetime < check_in_plus_8hrs or check_out_datetime < grace_end_datetime:
                duration_td = grace_end_datetime - check_out_datetime
                duration_str = str(duration_td)[:-3]
                early_going_case = {
                    "case": "early_going",
                    "from_date": check_out_datetime,
                    "to_date": grace_end_datetime,
                    "duration": duration_str
                }
        
        # Return the cases, or empty dictionaries if no event was found
        return early_going_case or {}, late_coming_case or {}


    def _process_submission(self, form):
        form.instance.is_submitted = True
        regularization_hr = (form.instance.to_date - form.instance.from_date).total_seconds() / 3600
        if form.instance.reg_status != settings.MIS_PUNCHING:
            max_hr_setting = self._get_app_setting("REGULARIZATION_MAX_HR")
            max_hr = int(getattr(max_hr_setting, "value", 2))
            if not getattr(max_hr_setting, 'beyond_policy', False) and regularization_hr > max_hr:
                messages.error(
                    self.request,
                    _(f"You can only regularize up to {max_hr}) hrs.")
                )
                return self.form_invalid(form)

        self.object = form.save()
        self.object.add_action(
            action="Submitted regularization",
            performed_by=self.request.user,
            comment=form.instance.reason,
        )
        messages.success(self.request, _("Regularization updated successfully."))
        self.send_notification(self.object)
        return HttpResponseRedirect(reverse("event_detail", kwargs={"slug": self.object.slug}))
    
    def send_notification(self, log):
        """Send notification for regularization."""
        current_site = Site.objects.get_current()
        protocol = "http"  # or 'https' if needed
        domain = current_site.domain
        try:
            send_regularization_notification.delay(log.id, protocol, domain)
        except Exception as e:
            pass

class AttendanceLogActionView(ModelPermissionRequiredMixin,View):
    model = AttendanceLog
    permission_action = "change"
    
    def fetch_static_data(self):
        """Fetch static data used in attendance calculations."""
        return {
            "half_day_color": AttendanceStatusColor.objects.get(
                status=settings.HALF_DAY
            ),
            "present_color": AttendanceStatusColor.objects.get(status=settings.PRESENT),
            "absent_color": AttendanceStatusColor.objects.get(status=settings.ABSENT),
            "asettings": AttendanceSetting.objects.first(),
        }

    def get_users(self, username):
        """Retrieve users based on username or all users if not specified."""
        queryset = User.objects.all().select_related("personal_detail")
        return queryset.filter(username=username) if username else queryset

    def parse_dates(self, from_date_str, to_date_str):
        """Parse string dates into timezone-aware datetime objects."""
        parse_date = lambda d: (
            make_aware(datetime.strptime(d, "%Y-%m-%d")) if d else None
        )
        return parse_date(from_date_str), parse_date(to_date_str)

    def get_user_shift(self, user):
        """Retrieve the shift timing for a given user."""
        emp_shift = (
            EmployeeShift.objects.filter(employee=user)
            .select_related("shift_timing")
            .first()
        )
        return emp_shift.shift_timing if emp_shift else None

    def handle_attendance_update(self, log, form_data, static_data):
        """Update attendance log with approval adjustments."""
        AttendanceLogHistory.objects.create(
            attendance_log=log,
            previous_data=make_json_serializable(model_to_dict(log)),
            modified_by=self.request.user,
        )

        reason = form_data["reason"]
        self.update_log_dates(log)

        status_handler = AttendanceStatusHandler(
            self.get_user_shift(log.applied_by),
            static_data["asettings"].full_day_hours,
            static_data["half_day_color"],
            static_data["present_color"],
            static_data["absent_color"],
        )
        status_data = self.calculate_status_data(log, static_data, status_handler)
        self.update_log_status(log, status_data)

        log.regularized = True
        log.save()
        log.approve(action_by=self.request.user, reason=reason)
        return _("Attendance log approved and updated successfully.")

    def update_log_dates(self, log):
        """Adjust the start and end dates for early-going and late-coming logs."""
        if log.reg_status == settings.EARLY_GOING:
            log.end_date = log.to_date
        elif log.reg_status == settings.LATE_COMING:
            log.start_date = log.from_date
        else:
            log.start_date = log.from_date
            log.end_date = log.to_date
        log.save()

    def calculate_status_data(self, log, static_data, status_handler):
        """Calculate the attendance status and return necessary data."""
        log_start_date = localtime(log.start_date)
        log_end_date = localtime(log.end_date)
        total_duration = log_end_date - log_start_date
        user_expected_logout_time = log_start_date + timedelta(
            hours=static_data["asettings"].full_day_hours
        )

        return status_handler.determine_attendance_status(
            log_start_date,
            log_end_date,
            total_duration,
            user_expected_logout_time.time(),
            user_expected_logout_time,
        )

    def update_log_status(self, log, status_data):
        """Update the log with the calculated status data."""
        (
            log.att_status,
            log.color_hex,
            log.reg_status,
            log.is_regularisation,
            log.from_date,
            log.to_date,
            log.reg_duration,
            log.status,
            log.att_status_short_code,
        ) = status_data
        total_minutes = (log.end_date - log.start_date).total_seconds() // 60

        # Calculate hours and minutes
        hours = total_minutes // 60
        minutes = total_minutes % 60
        log.duration = f"{int(hours):02}:{int(minutes):02}"

    def handle_action(self, action, log, form, static_data):
        """Handle the action specified in the form."""
        reason = form.cleaned_data["reason"]
        action_handlers = {
            "approve": lambda: self.handle_attendance_update(
                log, form.cleaned_data, static_data
            ),
            "reject": lambda: log.reject(action_by=self.request.user, reason=reason),
            "recommend": lambda: log.recommend(
                action_by=self.request.user, reason=reason
            ),
            "notrecommend": lambda: log.notrecommend(
                action_by=self.request.user, reason=reason
            ),
        }

        if action in action_handlers:
            return action_handlers[action]()
        else:
            return _("Invalid action.")

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        log_id = kwargs.get("slug")
        log = get_object_or_404(AttendanceLog, slug=log_id)
        form = AttendanceLogActionForm(request.POST)

        if form.is_valid():
            static_data = self.fetch_static_data()
            try:
                message = self.handle_action(action, log, form, static_data)
                messages.success(request, message)
            except Exception as e:
                messages.error(request, _("Error handling action: %s" % str(e)))
            self.send_notification(log)
            return HttpResponseRedirect(
                reverse("event_detail", kwargs={"slug": log.slug})
            )

        messages.error(request, _("Invalid action or form data."))
        return HttpResponseRedirect(reverse("event_detail", kwargs={"slug": log.slug}))

    def send_notification(self, log):
        """Send notification for regularization."""
        current_site = Site.objects.get_current()
        protocol = "http"  # or 'https' if needed
        domain = current_site.domain
        try:
            send_regularization_notification.delay(log.id, protocol, domain)
        except Exception as e:
            pass


def make_json_serializable(data):
    """Ensure data is JSON serializable."""
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))

class EventListView(View):
    def get(self, request, *args, **kwargs):
        user_id = request.GET.get("employee", self.request.user.id)
        start_param = request.GET.get("start")
        end_param = request.GET.get("end")

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)

        # Parse date filters if available
        start_date = datetime.fromisoformat(start_param) if start_param else None
        end_date = datetime.fromisoformat(end_param) if end_param else None
        check_in_time, check_out_time = at.get_check_in_out_times(user)
        events_data = []
        if check_in_time:
            events_data.append({
                "id": user.pk,
                "title": "Punched In",
                "start": timezone.localtime(timezone.make_aware(check_in_time)).isoformat(),
                "url": "#!",
            })
        # Holidays
        holidays = Holiday.objects.all()
        if start_date and end_date:
            holidays = holidays.filter(
                end_date__gte=start_date.date(), start_date__lte=end_date.date()
            )

        for holiday in holidays:
            events_data.append({
                "id": holiday.pk,
                "title": holiday.title,
                "start": timezone.localtime(timezone.make_aware(
                    datetime.combine(holiday.start_date, datetime.min.time())
                )).isoformat(),
                "end": timezone.localtime(timezone.make_aware(
                    datetime.combine(holiday.end_date, datetime.min.time()) + timedelta(days=1)
                )).isoformat(),
                "color": holiday.color_hex,
                "url": "#!",
            })

        # User-related data
        attendances = AttendanceLog.objects.filter(applied_by=user)
        leave_applications = LeaveApplication.objects.filter(appliedBy=user)
        tour_applications = UserTour.objects.filter(applied_by=user)
        office_closers = OfficeClosure.objects.all()

        if start_date and end_date:
            attendances = attendances.filter(end_date__gte=start_date, start_date__lte=end_date)
            leave_applications = leave_applications.filter(
                endDate__gte=start_date.date(), startDate__lte=end_date.date()
            )
            tour_applications = tour_applications.filter(
                end_date__gte=start_date.date(), start_date__lte=end_date.date()
            )
            office_closers = office_closers.filter(
                date__gte=start_date.date(), date__lte=end_date.date()
            )

        # Step 1: Collect all office closer dates
        closed_dates = set()
        for office_closer in office_closers:
            closed_date = office_closer.date
            closed_dates.add(closed_date)
            
            events_data.append({
                "id": office_closer.pk,
                "title": office_closer.reason,
                "start": timezone.localtime(timezone.make_aware(
                    datetime.combine(closed_date, datetime.min.time())
                )).isoformat(),
                "end": timezone.localtime(timezone.make_aware(
                    datetime.combine(closed_date, datetime.min.time()) + timedelta(days=1)
                )).isoformat(),
                "url": "#!",
            })
            events_data.append({
                "id": office_closer.pk,
                "title": "Present",
                "start": timezone.localtime(timezone.make_aware(
                    datetime.combine(closed_date, datetime.min.time())
                )).isoformat(),
                "end": timezone.localtime(timezone.make_aware(
                    datetime.combine(closed_date, datetime.min.time()) + timedelta(days=1)
                )).isoformat(),
                "color":"#06B900",
                "url": "#!",
            })

        # Step 2: Add attendance only if it doesn't fall on closed dates
        for att in attendances:
            att_start_date = timezone.localtime(att.start_date).date()
            att_end_date = timezone.localtime(att.end_date).date()

            # Check if any date in this attendance range overlaps with closed dates
            current = att_start_date
            overlaps = False
            while current <= att_end_date:
                if current in closed_dates:
                    overlaps = True
                    break
                current += timedelta(days=1)

            if not overlaps:
                base_event = {
                    "id": att.slug,
                    "start": timezone.localtime(att.start_date).isoformat(),
                    "end": timezone.localtime(att.end_date).isoformat(),
                    "url": reverse_lazy("event_detail", kwargs={"slug": att.slug}),
                }
                events_data.append({**base_event, "title": att.att_status, "color": att.color_hex})
                if att.regularized:
                    events_data.append({**base_event, "title": "Regularized"})

        # Tours
        for tour in tour_applications:
            events_data.append({
                "id": tour.slug,
                "title": f"Tour -> {tour.status}",
                "start": timezone.localtime(timezone.make_aware(
                    datetime.combine(tour.start_date, tour.start_time)
                )).isoformat(),
                "end": timezone.localtime(timezone.make_aware(
                    datetime.combine(tour.end_date, tour.end_time)
                )).isoformat(),
                "url": reverse_lazy("tour_application_detail", kwargs={"slug": tour.slug}),
                "color" : "#B1B1B1" if tour.status == settings.PENDING else "#3a87ad"
            })

        # Leaves
        for leave in leave_applications:
            events_data.append({
                "id": leave.slug,
                "title": f"{leave.leave_type.leave_type} {leave.status}",
                "start": timezone.localdate(leave.startDate).isoformat(),
                "end": (datetime.combine(timezone.localdate(leave.endDate), datetime.min.time()) + timedelta(days=1)).isoformat(),
                "color": leave.leave_type.color_hex if not leave.status == settings.PENDING else "#B1B1B1",
                "url": reverse_lazy("leave_application_detail", kwargs={"slug": leave.slug}),
            })


        return JsonResponse(events_data, safe=False)


from django.utils.dateparse import parse_date, parse_datetime


class AttendanceLogListView(ModelPermissionRequiredMixin, SingleTableMixin, FilterView):
    model = AttendanceLog
    table_class = AttendanceLogTable
    template_name = "hrms_app/regularization.html"
    context_object_name = "attendance_logs"
    paginate_by = 100
    permission_action = "view"
    filterset_class = AttendanceLogFilter
    title = _("Regularizations")

    def get_date_range(self):
        """Extracts date range from GET params or defaults to current month."""
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        if start_date and end_date:
            try:
                start_date = parse_datetime(start_date) or parse_date(start_date)
                end_date = parse_datetime(end_date) or parse_date(end_date)
            except Exception:
                start_date = end_date = None
        if not start_date or not end_date:
            today = now().date()
            start_date = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month.replace(day=1) - timedelta(days=1)
        return start_date, end_date

    def filter_by_date_range(self, queryset):
        start_date, end_date = self.get_date_range()
        if start_date and end_date:
            return queryset.filter(
                start_date__gte=start_date,
                end_date__lte=end_date,
            )
        return queryset

    def get_queryset(self):
        user = self.request.user
        qs_current_user = self.model.objects.none()
        qs_current_user = self.model.objects.filter(
            applied_by=user, is_regularisation=True, status=settings.PENDING
        )
        qs_current_user
        return self.filter_by_date_range(qs_current_user)

    def get_assigned_users_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            qs_all = self.model.objects.filter(
                is_regularisation=True, status=settings.PENDING
            ).exclude(pk=user.pk).order_by("applied_by__first_name")
            return self.filter_by_date_range(qs_all)

        if hasattr(user, "employees"):
            qs = self.model.objects.filter(
                applied_by__in=user.employees.all(),
                is_regularisation=True,is_submitted=True,
                status=settings.PENDING
            )
            return self.filter_by_date_range(qs)
        return self.model.objects.none()

    def get_filterset(self, filterset_class):
        return filterset_class(
            self.request.GET, queryset=self.get_queryset()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.get_filterset(self.filterset_class)
        context["assigned_regs"] = self.get_assigned_users_queryset()
        context.update({"title": self.title})
        return context


class ChangePasswordView(LoginRequiredMixin, FormView):
    template_name = "hrms_app/change-password.html"
    form_class = ChangeUserPasswordForm
    success_url = reverse_lazy("login")
    error_message = "Error while changing the password. Please try again"

    def form_valid(self, form):
        custom_user = self.request.user
        custom_user.is_password_changed = True
        custom_user.save()
        form.save()
        messages.success(
            self.request,
            "Your password was changed successfully. Please Login again to continue...",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, self.error_message)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["error_message"] = self.error_message
        context["form_errors"] = self.get_form().errors  # Corrected line
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

from django_tables2.views import MultiTableMixin


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
        tour = form.save(commit=False)
        user = self.request.user
        attendance_log = AttendanceLog.objects.filter(applied_by=user,start_date__date=tour.start_date,regularized=True).last()
        log_history = AttendanceLogHistory.objects.filter(attendance_log=attendance_log).last()
        if log_history:
            data = log_history.previous_data
            from_date = localtime(at.str_to_date(data["from_date"]))
            to_date = localtime(at.str_to_date(data["to_date"]))
            status = data['reg_status']
            if status == "late coming" and tour.end_time > from_date.time():
                messages.error(self.request, f"Tour end time on {tour.start_date.strftime('%d %b %Y')} conflicts with regularization time.")
                return self.form_invalid(form)
            if status == "early going" and tour.start_time < to_date.time():
                messages.error(self.request, f"Tour start time on {tour.start_date.strftime('%d %b %Y')} conflicts with regularization time.")
                return self.form_invalid(form)
        overlapping_leaves = LeaveApplication.objects.filter(
            appliedBy=user,
            status__in=[settings.APPROVED, settings.PENDING, settings.PENDING_CANCELLATION],
            startDayChoice=settings.FULL_DAY,
            endDayChoice=settings.FULL_DAY,
            startDate__lte=tour.end_date,
            endDate__gte=tour.start_date
        )
        if overlapping_leaves:
            shifts = getattr(user, 'shifts', None)
            if not shifts:
                messages.error(self.request, "Shift details not found.")
                return self.form_invalid(form)
            shift = shifts.last().shift_timing
            shift_start = shift.start_time
            shift_end = shift.end_time
            for leave in overlapping_leaves:
                leave_dates = [
                    localtime(leave.startDate)+ timedelta(days=i)
                    for i in range((leave.endDate - leave.startDate).days + 1)
                ]
                for leave_date in leave_dates:
                    if tour.end_date == leave_date.date():
                        if tour.end_time >= shift_start:
                            messages.error(self.request, f"Tour end time on {leave_date.date().strftime('%d %b %Y')} conflicts with full-day leave.")
                            return self.form_invalid(form)
                    if tour.start_date == leave_date.date():
                        if tour.start_time <= shift_end:
                            messages.error(self.request, f"Tour start time on {leave_date.date().strftime('%d %b %Y')} conflicts with full-day leave.")
                            return self.form_invalid(form)
                        
        tour.applied_by = user
        messages.success(self.request, "Tour Applied Successfully")
        # self.send_tour_notification(obj=tour)
        # return super().form_valid(form)
        return redirect("apply_tour")

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
    
    def send_tour_notification(self,obj):
        current_site = Site.objects.get_current()
        protocol = 'http'  # or 'https' if applicable
        domain = current_site.domain
        try:
            send_tour_notifications.delay(obj.id, protocol, domain)
        except:
            pass


class TourApplicationDetailView(ModelPermissionRequiredMixin, UpdateView):
    model = UserTour
    template_name = "hrms_app/tour_application_detail.html"
    context_object_name = "tour_application"
    form_class = TourStatusUpdateForm
    slug_field = "slug"
    slug_url_kwarg = "slug"
    permission_action = "change"

    def get_object(self, queryset=None):
        tour_application = super().get_object(queryset)
        user = self.request.user
        if (
            tour_application.applied_by == user
            or user.is_superuser
            or user.is_staff
            or user.personal_detail.designation.department.department == "admin"
            or tour_application.applied_by.reports_to == user
        ):
            return tour_application
        raise PermissionDenied(
            "Only Employee, Manager and Admin can view His/Her tour details."
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tour_application = self.get_object()
        kwargs["user"] = self.request.user
        kwargs["is_manager"] = (
            self.request.user == tour_application.applied_by.reports_to
        )
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        messages.success(
            self.request,
            f"Tour {form.cleaned_data.get('status')} Successfully",
        )
        TourStatusLog.create_log(
            tour=self.object,
            action_by=self.request.user,
            action=form.cleaned_data.get("status"),
            comments=form.cleaned_data.get("reason"),
        )
        return HttpResponseRedirect(
            reverse("tour_application_detail", kwargs={"slug": self.object.slug})
        )

    def form_invalid(self, form, msg=None):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tour_application = self.get_object()
        current_url = self.request.get_full_path()

        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("tour_tracker", {"label": "Tour Tracker"}),
            (
                "tour_application_detail",
                {"label": f"{tour_application.slug}", "slug": tour_application.slug},
            ),
        ]
        context["is_manager"] = (
            self.request.user == tour_application.applied_by.reports_to
        )
        # Add the 'next' parameter to the delete URL
        context["delete_url"] = reverse(
            "generic_delete",
            kwargs={"model_name": self.model.__name__, "pk": self.get_object().pk},
        )
        context["delete_url"] += "?" + urlencode({"next": reverse("tour_tracker")})
        context["is_locked"] = self.get_lock_status(tour=tour_application)

        # Add the 'next' parameter to the edit URL
        context["edit_url"] = reverse(
            "tour_application_update", kwargs={"slug": self.get_object().slug}
        )
        context["edit_url"] += "?" + urlencode({"next": current_url})

        context["pdf_url"] = reverse(
            "generate_tour_pdf", kwargs={"slug": self.get_object().slug}
        )
        context["urls"] = urls
        return context

    def get_success_url(self):
        return reverse_lazy(
            "tour_application_detail", kwargs={"slug": self.object.slug}
        )

    def get_lock_status(self, tour):
        lock_status = LockStatus.objects.filter(
            from_date__lte=tour.start_date, to_date__gte=tour.end_date
        )
        return lock_status.exists()


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
    
    def send_tour_notification(self,obj):
        current_site = Site.objects.get_current()
        protocol = 'http'  # or 'https' if applicable
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


from django.http import HttpResponse
from weasyprint import HTML
from django.template.loader import render_to_string


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


class CustomUploadView(View):
    @csrf_exempt
    def post(self, request, *args, **kwargs):
        file = request.FILES.get("upload")
        if file:
            file_name = default_storage.save(file.name, ContentFile(file.read()))
            file_url = default_storage.url(file_name)
            response = {
                "url": file_url,
                "uploaded": True,
                "message": "File uploaded successfully",
            }
        else:
            response = {"uploaded": False, "message": "No file uploaded"}
        return JsonResponse(response)

@method_decorator(login_required,name="dispatch")
class EmployeeListView(LoginRequiredMixin, ListView):
    model = CustomUser
    template_name = "hrms_app/employee/employees.html"
    context_object_name = "users"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # First, enforce login requirement
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Then, enforce staff or superuser check
        if not (request.user.is_staff or request.user.is_superuser):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = CustomUser.objects.all()

        # Filter by active status if provided in GET params
        is_active = self.request.GET.get("is_active")
        if is_active is not None and is_active != "":
            queryset = queryset.filter(is_active=is_active)

        # Search by username, first name, last name, or email
        search_query = self.request.GET.get("q")
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(official_email__icontains=search_query)
            )

        return queryset.order_by("first_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        context["is_active"] = self.request.GET.get("is_active", "")
        context["urls"] = [
            ("dashboard", {"label": "Dashboard"}),
            ("employees", {"label": "Employee List"}),
        ]
        return context


class LeaveTransactionCreateView(FormView):
    form_class = LeaveTransactionForm
    template_name = "hrms_app/leave_transaction.html"
    title = _("Leave Transaction")

    def get_success_url(self):
        # Redirect back to the same form for creating a new transaction
        return reverse_lazy("leave_transaction_create")

    def form_valid(self, form):
        try:
            # Process the form and create transactions
            form.process()
            messages.success(self.request, "Leave transaction applied successfully.")
        except ValueError as e:
            messages.error(self.request, f"Error: {e}")
            return self.form_invalid(form)  # Return form with errors if process fails
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        # Add an error message and render the form again
        messages.error(
            self.request,
            "There was an error with your submission. Please check the form and try again.",
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        urls = [
            ("dashboard", {"label": "Dashboard"}),
            ("leave_transaction_create", {"label": "Leave Transaction"}),
        ]
        context.update({"urls": urls, "title": self.title})
        return context


class LeaveBalanceUpdateView(View):
    template_name = "hrms_app/leave_bal_up.html"

    def get(self, request, *args, **kwargs):
        form = LeaveBalanceForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        form = LeaveBalanceForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get("user")
            leave_type = form.cleaned_data["leave_type"]
            year = form.cleaned_data["year"]
            opening_balance = form.cleaned_data.get("opening_balance")
            closing_balance = form.cleaned_data.get("closing_balance")
            no_of_leaves = form.cleaned_data.get("no_of_leaves")
            remaining_leave_balances = form.cleaned_data.get("remaining_leave_balances")

            try:
                with transaction.atomic():
                    if user:
                        # Update only for the selected user
                        leave_balances = LeaveBalanceOpenings.objects.filter(
                            user=user, leave_type=leave_type, year=year
                        )
                    else:
                        # Update for all users with the selected leave type
                        leave_balances = LeaveBalanceOpenings.objects.filter(
                            leave_type=leave_type, year=year
                        )

                    if leave_balances.exists():
                        for balance in leave_balances:
                            if opening_balance is not None:
                                balance.opening_balance = opening_balance
                            if closing_balance is not None:
                                balance.closing_balance = closing_balance
                            if no_of_leaves is not None:
                                balance.no_of_leaves = no_of_leaves
                            if remaining_leave_balances is not None:
                                balance.remaining_leave_balances = (
                                    remaining_leave_balances
                                )
                            balance.save(
                                update_fields=[
                                    "opening_balance",
                                    "closing_balance",
                                    "no_of_leaves",
                                    "remaining_leave_balances",
                                ]
                            )

                        messages.success(
                            request, "Leave balances updated successfully."
                        )
                    else:
                        # If no leave balances exist, create them
                        messages.warning(request, "No existing leave balances found.")
                        if user:
                            LeaveBalanceOpenings.objects.create(
                                user=user,
                                leave_type=leave_type,
                                year=year,
                                opening_balance=opening_balance or 0,
                                closing_balance=closing_balance or 0,
                                no_of_leaves=no_of_leaves or 0,
                                remaining_leave_balances=remaining_leave_balances or 0,
                                created_by=request.user,
                            )
                        else:
                            for user in CustomUser.objects.all():
                                LeaveBalanceOpenings.objects.create(
                                    user=user,
                                    leave_type=leave_type,
                                    year=year,
                                    opening_balance=opening_balance or 0,
                                    closing_balance=closing_balance or 0,
                                    no_of_leaves=no_of_leaves or 0,
                                    remaining_leave_balances=remaining_leave_balances
                                    or 0,
                                    created_by=request.user,
                                )
                        messages.success(
                            request, "New leave balances created successfully."
                        )
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")
            return redirect("leave_bal_up")
        return render(request, self.template_name, {"form": form})
