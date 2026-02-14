from hrms_app.models import *
import unicodedata
from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from hrms_app.utility.leave_utils import LeavePolicyManager, LeaveStatsManager
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import capfirst
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget
from colorfield.widgets import ColorWidget
from django.core.validators import RegexValidator
from bootstrap_datepicker_plus.widgets import (
    DatePickerInput,
    TimePickerInput,
    DateTimePickerInput,
)

User = get_user_model()


def _unicode_ci_compare(s1, s2):
    """
    Perform case-insensitive comparison of two identifiers, using the
    recommended algorithm from Unicode Technical Report 36, section
    2.11.2(B)(2).
    """
    return (
            unicodedata.normalize("NFKC", s1).casefold()
            == unicodedata.normalize("NFKC", s2).casefold()
    )


class ReadOnlyPasswordHashWidget(forms.Widget):
    template_name = "auth/widgets/read_only_password_hash.html"
    read_only = True

    def get_context(self, name, value, attrs):
        # sourcery skip: for-append-to-extend
        context = super().get_context(name, value, attrs)
        summary = []
        if not value or value.startswith(UNUSABLE_PASSWORD_PREFIX):
            summary.append({"label": gettext("No password set.")})
        else:
            try:
                hasher = identify_hasher(value)
            except ValueError:
                summary.append(
                    {
                        "label": gettext(
                            "Invalid password format or unknown hashing algorithm."
                        )
                    }
                )
            else:
                for key, value_ in hasher.safe_summary(value).items():
                    summary.append({"label": gettext(key), "value": value_})
        context["summary"] = summary
        return context

    def id_for_label(self, id_):
        return None


class ReadOnlyPasswordHashField(forms.Field):
    widget = ReadOnlyPasswordHashWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("disabled", True)
        super().__init__(*args, **kwargs)


class UsernameField(forms.CharField):
    def to_python(self, value):
        value = super().to_python(value)
        if self.max_length is not None and len(value) > self.max_length:
            # Normalization can increase the string length (e.g.
            # "ﬀ" -> "ff", "½" -> "1⁄2") but cannot reduce it, so there is no
            # point in normalizing invalid data. Moreover, Unicode
            # normalization is very slow on Windows and can be a DoS attack
            # vector.
            return value
        return unicodedata.normalize("NFKC", value)

    def widget_attrs(self, widget):
        return {
            **super().widget_attrs(widget),
            "autocapitalize": "none",
            "autocomplete": "username",
        }


class BaseUserCreationForm(forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given username and
    password.
    """

    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
    }
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text=_("Enter the same password as before, for verification."),
    )

    class Meta:
        model = User
        fields = ("username",)
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._meta.model.USERNAME_FIELD in self.fields:
            self.fields[self._meta.model.USERNAME_FIELD].widget.attrs[
                "autofocus"
            ] = True

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
        return password2

    def _post_clean(self):
        super()._post_clean()
        # Validate the password after self.instance is updated with form data
        # by super().
        password = self.cleaned_data.get("password2")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            if hasattr(self, "save_m2m"):
                self.save_m2m()
        return user


class UserCreationForm(BaseUserCreationForm):
    def clean_username(self):
        """Reject usernames that differ only in case."""
        username = self.cleaned_data.get("username")
        if (
                username
                and self._meta.model.objects.filter(username__iexact=username).exists()
        ):
            self._update_errors(
                ValidationError(
                    {
                        "username": self.instance.unique_error_message(
                            self._meta.model, ["username"]
                        )
                    }
                )
            )
        else:
            return username


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_(
            "Raw passwords are not stored, so there is no way to see this "
            "user’s password, but you can change the password using "
            '<a href="{}">this form</a>.'
        ),
    )

    class Meta:
        model = User
        fields = "__all__"
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password = self.fields.get("password")
        if password:
            password.help_text = password.help_text.format(
                f"../../{self.instance.pk}/password/"
            )
        user_permissions = self.fields.get("user_permissions")
        if user_permissions:
            user_permissions.queryset = user_permissions.queryset.select_related(
                "content_type"
            )


class AuthenticationForm(forms.Form):
    """
    Base class for authenticating users. Extend this to get a form that accepts
    username/password logins.
    """

    username = UsernameField(
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "data-append": "<span class='mif-envelop'>",
                "data-validate": "required",
                "data-role": "input",
                "autofocus": True,
                "class": "form-control",
                "placeholder": "Enter username",
            }
        )
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "type": "password",
                "data-append": "<span class='mif-key'>",
                "data-validate": "required",
                "data-role": "input",
                "autocomplete": "current-password",
                "class": "form-control",
                "placeholder": "Enter password",
            }
        ),
    )
    error_messages = {
        "invalid_login": _(
            "Please enter a correct %(username)s and password. Note that both "
            "fields may be case-sensitive."
        ),
        "inactive": _("This account is inactive."),
    }

    def __init__(self, request=None, *args, **kwargs):
        """
        The 'request' parameter is set for custom auth use by subclasses.
        The form data comes in via the standard 'data' kwarg.
        """
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

        # Set the max length and label for the "username" field.
        self.username_field = User._meta.get_field(User.USERNAME_FIELD)
        username_max_length = self.username_field.max_length or 254
        self.fields["username"].max_length = username_max_length
        self.fields["username"].widget.attrs["maxlength"] = username_max_length
        if self.fields["username"].label is None:
            self.fields["username"].label = capfirst(self.username_field.verbose_name)

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        """
        Controls whether the given User may log in. This is a policy setting,
        independent of end-user authentication. This default behavior is to
        allow login by active users, and reject login by inactive users.

        If the given user cannot log in, this method should raise a
        ``ValidationError``.

        If the given user may log in, this method should return None.
        """
        if not user.is_active:
            raise ValidationError(
                self.error_messages["inactive"],
                code="inactive",
            )

    def get_user(self):
        return self.user_cache

    def get_invalid_login_error(self):
        return ValidationError(
            self.error_messages["invalid_login"],
            code="invalid_login",
            params={"username": self.username_field.verbose_name},
        )


class PasswordResetForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def send_mail(
            self,
            subject_template_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name=None,
    ):
        """
        Send a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        email_message.send()

    def get_users(self, email):
        # sourcery skip: replace-interpolation-with-fstring
        """Given an email, return matching user(s) who should receive a reset.

        This allows subclasses to more easily customize the default policies
        that prevent inactive users and users with unusable passwords from
        resetting their password.
        """
        email_field_name = "official_email"
        # email_field_name = User.get_email_field_name()
        active_users = User._default_manager.filter(
            **{
                "%s__iexact" % email_field_name: email,
                "is_active": True,
            }
        )

        # active_users = User._default_manager.filter(
        # official_email__iexact=email,
        # is_active=True)

        return (
            u
            for u in active_users
            if u.has_usable_password()
               and _unicode_ci_compare(email, getattr(u, email_field_name))
        )

    def save(
            self,
            domain_override=None,
            subject_template_name="registration/password_reset_subject.txt",
            email_template_name="registration/password_reset_email.html",
            use_https=False,
            token_generator=default_token_generator,
            from_email=None,
            request=None,
            html_email_template_name=None,
            extra_email_context=None,
    ):
        """
        Generate a one-use only link for resetting password and send it to the
        user.
        """
        email = self.cleaned_data["email"]
        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override
        # email_field_name = User.get_email_field_name()
        email_field_name = "official_email"
        for user in self.get_users(email):
            user_email = getattr(user, email_field_name)
            context = {
                "email": user_email,
                "domain": domain,
                "site_name": site_name,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "token": token_generator.make_token(user),
                "protocol": "https" if use_https else "http",
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user_email,
                html_email_template_name=html_email_template_name,
            )


class SetPasswordForm(forms.Form):
    """
    A form that lets a user set their password without entering the old
    password
    """

    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
    }
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": "form-control",
            }
        ),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": "form-control",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
        password_validation.validate_password(password2, self.user)
        return password2

    def save(self, commit=True):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class PasswordChangeForm(SetPasswordForm):
    """
    A form that lets a user change their password by entering their old
    password.
    """

    error_messages = {
        **SetPasswordForm.error_messages,
        "password_incorrect": _(
            "Your old password was entered incorrectly. Please enter it again."
        ),
    }
    old_password = forms.CharField(
        label=_("Old password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "autofocus": True}
        ),
    )

    field_order = ["old_password", "new_password1", "new_password2"]

    def clean_old_password(self):
        """
        Validate that the old_password field is correct.
        """
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise ValidationError(
                self.error_messages["password_incorrect"],
                code="password_incorrect",
            )
        return old_password


class AdminPasswordChangeForm(forms.Form):
    """
    A form used to change the password of a user in the admin interface.
    """

    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
    }
    required_css_class = "required"
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "autofocus": True}
        ),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password (again)"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text=_("Enter the same password as before, for verification."),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
        password_validation.validate_password(password2, self.user)
        return password2

    def save(self, commit=True):
        """Save the new password."""
        password = self.cleaned_data["password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user

    @property
    def changed_data(self):  # sourcery skip: use-next
        data = super().changed_data
        for name in self.fields:
            if name not in data:
                return []
        return ["password"]


from datetime import datetime, timedelta


class SetPasswordForm(forms.Form):
    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
    }
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "data-role": "input",
                "data-prepend": "New password: ",
            }
        ),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "data-role": "input",
                "data-prepend": "New password confirmation: ",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
        password_validation.validate_password(password2, self.user)
        return password2

    def save(self, commit=True):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class ChangeUserPasswordForm(SetPasswordForm):
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_incorrect": _(
            "Your old password was entered incorrectly. Please enter it again."
        ),
    }
    old_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "autofocus": True,
                "data-role": "input",
                "class": "form-control",
                "data-prepend": "Old Password: ",
            }
        ),
    )
    field_order = ["old_password", "new_password1", "new_password2"]

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"].strip()
        if not self.user.check_password(old_password):
            raise ValidationError(
                self.error_messages["password_incorrect"],
                code="password_incorrect",
            )
        return old_password


class ExcelUploadForm(forms.Form):
    file = forms.FileField()

from hrms_app.utility import attendanceutils as at
from django.utils.timezone import localtime
from hrms_app.utility.leave_utils import get_non_working_days

class TourForm(forms.ModelForm):
    approval_type = forms.ChoiceField(
        choices=settings.APPROVAL_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Approval Type"),
        required=True,
    )

    class Meta:
        model = UserTour
        fields = [
            "approval_type", "from_destination", "start_date", "start_time",
            "to_destination", "end_date", "end_time", "remarks",
        ]
        widgets = {
            "from_destination": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": DatePickerInput(
                options={"format": "DD MMM, YYYY", "showClear": True, "showClose": True, "useCurrent": False},
                attrs={"class": "form-control"},
            ),
            "start_time": TimePickerInput(
                options={"format": "hh:mm A", "showClear": True, "showClose": True, "useCurrent": False},
                attrs={"class": "form-control"},
            ),
            "end_date": DatePickerInput(
                options={"format": "DD MMM, YYYY", "showClear": True, "showClose": True, "useCurrent": False},
                range_from="start_date",
                attrs={"class": "form-control"},
            ),
            "end_time": TimePickerInput(
                options={"format": "hh:mm A", "showClear": True, "showClose": True, "useCurrent": False},
                attrs={"class": "form-control"},
            ),
            "to_destination": forms.TextInput(attrs={"class": "form-control"}),
            "remarks": CKEditor5Widget(config_name="extends"),
        }
        labels = {
            "from_destination": _("Boarding"),
            "start_date": _("Start Date"),
            "start_time": _("Start Time"),
            "end_date": _("End Date"),
            "end_time": _("End Time"),
            "to_destination": _("Destination"),
            "remarks": _("Remark"),
        }

    def __init__(self, *args, **kwargs):
        # Extract user safely to use in validation
        self.user = kwargs.pop('user', None)
        super(TourForm, self).__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.required = True

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        approval_type = cleaned_data.get("approval_type")

        # 1. Basic Date Logic
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError(_("End date must be after start date."))
            if start_date == end_date and start_time and end_time and start_time >= end_time:
                raise ValidationError(_("End time must be after start time on the same day."))
        today = now().date()
        if approval_type == settings.PRE_APPROVAL and start_date and start_date < today:
            raise ValidationError(_("For Pre Approval, the start date must be today or a future date."))
        
        if approval_type == settings.POST_APPROVAL and start_date and start_date >= today:
            raise ValidationError(_("For Post Approval, the start date must be in the past."))
        
        if self.user and start_date and end_date:
            self._validate_attendance_conflict(start_date, end_time, start_time)
            self._validate_leave_conflict(start_date, end_date, start_time, end_time)
        self._apply_tour_policy(end_date)

        return cleaned_data
    
    def _apply_tour_policy(self,end_date):
        current_date = timezone.now().date()
        non_working_days = get_non_working_days(start=end_date,end=current_date)
        gap = (current_date - end_date).days + 1
        gap = gap - non_working_days
        app_setting = AppSetting.objects.filter(key="TOUR_LIMIT").first()
        if app_setting and app_setting.beyond_policy:
            return
        if gap > int(app_setting.value):
            raise ValidationError(f"Tour application denied.You can apply within {app_setting.value} working days.")


    def _validate_attendance_conflict(self, start_date, tour_end_time, tour_start_time):
        """Checks conflict with Regularized Attendance (Late Coming / Early Going)"""
        history = AttendanceLogHistory.objects.filter(
            attendance_log__applied_by=self.user,
            attendance_log__start_date__date=start_date,
            attendance_log__regularized=True
        ).select_related('attendance_log').order_by('-id').first()

        if history:
            data = history.previous_data
            from_date = localtime(at.str_to_date(data["from_date"])) 
            to_date = localtime(at.str_to_date(data["to_date"]))
            status = data["reg_status"]
            if status == "late coming" and tour_end_time > from_date.time():
                raise ValidationError(f"Tour end time on {start_date} conflicts with regularization time.")
            if status == "early going" and tour_start_time < to_date.time():
                raise ValidationError(f"Tour start time on {start_date} conflicts with regularization time.")
            pass

    def _validate_leave_conflict(self, start_date, end_date, start_time, end_time):
        """Checks conflict with Approved/Pending Leaves"""
        overlapping_leaves = LeaveApplication.objects.filter(
            appliedBy=self.user,
            status__in=[settings.APPROVED, settings.PENDING, settings.PENDING_CANCELLATION],
            startDayChoice=settings.FULL_DAY,
            endDayChoice=settings.FULL_DAY,
            startDate__lte=end_date,
            endDate__gte=start_date,
        )

        if overlapping_leaves.exists():
            shifts = getattr(self.user, "shifts", None)
            if not shifts:
                raise ValidationError("Shift details not found for leave conflict check.")
            
            # Optimized: Get shift once
            shift = shifts.last().shift_timing
            shift_start = shift.start_time
            shift_end = shift.end_time

            for leave in overlapping_leaves:
                # Check overlap logic
                leave_range = (leave.endDate - leave.startDate).days + 1
                for i in range(leave_range):
                    leave_day = leave.startDate + timedelta(days=i)
                    
                    if end_date == leave_day and end_time >= shift_start:
                        raise ValidationError(f"Tour end time on {leave_day} conflicts with full-day leave.")
                    
                    if start_date == leave_day and start_time <= shift_end:
                        raise ValidationError(f"Tour start time on {leave_day} conflicts with full-day leave.")

class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ["bill_amount", "bill_date", "bill_details", "bill_document"]


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = [
            "leave_type",
            "leave_type_short_code",
            "min_notice_days",
            "max_days_limit",
            "min_days_limit",
            "allowed_days_per_year",
            "default_allocation",
            "leave_fy_start",
            "leave_fy_end",
            "color_hex",
            "text_color_hex",
            "consecutive_restriction",
            "restricted_after_leave_types",
        ]
        widgets = {
            "color_hex": ColorWidget(),
            "text_color_hex": ColorWidget(),
        }


class CustomFileInput(forms.ClearableFileInput):
    template_name = "widgets/custom_file_input.html"  # Path to your custom template

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update(
            {
                "class": "custom-file-input",  # Add a CSS class
                "accept": ".pdf,.jpg,.jpeg,.png",  # Restrict file types
            }
        )


class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = [
            "leave_type",
            "startDate",
            "endDate",
            "leave_address",
            "startDayChoice",
            "endDayChoice",
            "usedLeave",
            "balanceLeave",
            "reason",
        ]
        widgets = {
            "startDate": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "endDate": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                range_from="startDate",
                attrs={"class": "form-control"},
            ),
            "startDayChoice": forms.Select(
                attrs={"class": "leaveOption id_startDayChoice"}
            ),
            "endDayChoice": forms.Select(
                attrs={"class": "leaveOption id_endDayChoice"}
            ),
            "usedLeave": forms.TextInput(
                attrs={"type": "text", "data-role": "input", "readonly": "readonly"}
            ),
            "leave_address": forms.TextInput(
                attrs={"type": "text", "class": "form-control"}
            ),
            "balanceLeave": forms.TextInput(
                attrs={"type": "text", "data-role": "input", "readonly": "readonly"}
            ),
            "reason": CKEditor5Widget(attrs={"class": "django_ckeditor_5"}),
        }
        labels = {
            "startDate": _("Start Date"),
            "endDate": _("End Date"),
            "usedLeave": _("Currently Booked"),
            "leave_address": _("Leave Address"),
            "balanceLeave": _("Available Balance"),
            "reason": _("Reason"),
            "startDayChoice": _("Start Day"),
            "endDayChoice": _("End Day"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        leave_type = kwargs.pop("leave_type", None)
        super(LeaveApplicationForm, self).__init__(*args, **kwargs)
        leave_type_obj = LeaveType.objects.filter(id=leave_type).first()
        stats = LeaveStatsManager(self.user, leave_type_obj)
        self.fields["balanceLeave"].initial = stats.get_remaining_balance(
            year=timezone.now().year
        )
        if leave_type_obj.leave_type_short_code == "SL":
            self.fields["attachment"] = forms.FileField(
                required=False,  # Initially not required
                label=_("Attachment"),
                help_text=_(
                    "Upload a medical certificate or supporting document (required for Sick Leave > 3 days)."
                ),
                widget=forms.ClearableFileInput(
                    attrs={
                        "class": "form-control-file",
                        "accept": ".pdf,.jpg,.jpeg,.png",
                    }
                ),
            )
        self.fields["leave_type"].initial = leave_type

    def clean(self):
        cleaned_data = super().clean()
        startDate = cleaned_data.get("startDate")
        endDate = cleaned_data.get("endDate")
        usedLeave = cleaned_data.get("usedLeave")
        leaveTypeId = cleaned_data.get("leave_type")
        startDayChoice = cleaned_data.get("startDayChoice")
        endDayChoice = cleaned_data.get("endDayChoice")
        attachment = cleaned_data.get("attachment")
        leave_address = cleaned_data.get("leave_address")
        reason = cleaned_data.get("reason")

        if not startDate or not endDate:
            if not startDate:
                self.add_error("startDate", _("Start Date is required."))
            if not endDate:
                self.add_error("endDate", _("End Date is required."))
            return cleaned_data

        if startDate > endDate:
            self.add_error("endDate", _("End Date must be after Start Date."))
            return cleaned_data
        if not leave_address:
            self.add_error("leave_address", _("Leave Address is required."))
        if not reason:
            self.add_error("reason", _("Reason is required."))

        if (
                leaveTypeId
                and leaveTypeId.leave_type_short_code == "SL"
                and usedLeave
                and int(usedLeave) > 3
        ):
            if not attachment:
                self.add_error(
                    "attachment",
                    _(
                        "Attachment is required for Sick Leave applications exceeding 3 days."
                    ),
                )

        exclude_application_id = (
            self.instance.id if self.instance and self.instance.pk else None
        )
        # Only validate policies if it's a new leave application (i.e., no instance.pk)
        if not self.instance or not self.instance.pk:
            try:
                policy_manager = LeavePolicyManager(
                    user=self.user,
                    leave_type=leaveTypeId,
                    start_date=startDate,
                    end_date=endDate,
                    start_day_choice=startDayChoice,
                    end_day_choice=endDayChoice,
                    bookedLeave=usedLeave,
                    exclude_application_id=exclude_application_id,
                )
                policy_manager.validate_policies()
            except ValidationError as e:
                self.add_error(None, str(e))
        return cleaned_data


class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = "__all__"
        widgets = {
            "color_hex": ColorWidget(),
        }


class AttendanceStatusColorForm(forms.ModelForm):
    class Meta:
        model = AttendanceStatusColor
        fields = "__all__"
        widgets = {
            "color_hex": ColorWidget(),
        }


class AttendanceLogFilterForm(forms.ModelForm):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Search by title or user", "class": "form-control"}
        ),
    )

    class Meta:
        model = AttendanceLog
        fields = ("reg_status", "status", "is_submitted", "is_regularisation")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_submitted"].initial = True


class AttendanceLogForm(forms.ModelForm):
    """
    Form for handling attendance log regularization requests.
    Dynamically adjusts fields and choices based on user role and attendance events.
    """
    
    class Meta:
        model = AttendanceLog
        fields = [
            "reg_status",
            "from_date", 
            "to_date",
            "status",
            "reg_duration",
            "reason",
        ]
        widgets = {
            "reg_status": forms.RadioSelect(attrs={"class": "form-input"}),
            "duration": TimePickerInput(
                attrs={"class": "form-control", "readonly": "readonly"}
            ),
            "reg_duration": forms.TextInput(
                attrs={"class": "form-control", "readonly": "readonly"}
            ),
            "from_date": DateTimePickerInput(
                options={
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                format="%Y-%m-%d %H:%M",
                attrs={"class": "form-control"},
            ),
            "to_date": DateTimePickerInput(
                options={
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                format="%Y-%m-%d %H:%M",
                attrs={"class": "form-control"},
                range_from="from_date",
            ),
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control", 
                    "rows": 3,
                    "placeholder": _("Please provide reason for regularization...")
                }
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        # Extract custom parameters
        self.user = kwargs.pop("user", None)
        self.is_manager = kwargs.pop("is_manager", False)
        self.late_coming = kwargs.pop("late_coming", {})
        self.early_going = kwargs.pop("early_going", {})
        
        super().__init__(*args, **kwargs)
        
        # Initialize form based on context
        self._setup_regularization_status_field()
        self._setup_user_role_specific_fields()
        self._setup_initial_values()

    def _setup_regularization_status_field(self):
        """Configure the reg_status field based on current instance and available events."""
        self.fields["reg_status"].required = True
        
        current_reg_status = getattr(self.instance, 'reg_status', None) if self.instance.pk else None
        
        if current_reg_status == settings.MIS_PUNCHING:
            self._set_mis_punching_choices()
        else:
            self._set_attendance_event_choices()

    def _set_mis_punching_choices(self):
        """Set choices for mis punching scenario."""
        self.fields["reg_status"].choices = [
            (settings.MIS_PUNCHING, _("Mis Punching")),
        ]

    def _set_attendance_event_choices(self):
        """Set choices based on available attendance events (late coming, early going)."""
        choices = []
        
        if self.early_going:
            choices.append((settings.EARLY_GOING, _("Early Going")))
        if self.late_coming:
            choices.append((settings.LATE_COMING, _("Late Coming")))
            
        if not choices:
            # Fallback if no events detected
            choices = [
                (settings.LATE_COMING, _("Late Coming")),
                (settings.EARLY_GOING, _("Early Going")),
            ]
            
        self.fields["reg_status"].choices = choices
        # Don't pre-select any option for new instances
        if not self.instance.pk:
            self.initial["reg_status"] = None

    def _setup_user_role_specific_fields(self):
        """Configure fields based on whether user is manager or employee."""
        if self.is_manager:
            self._setup_manager_fields()
        else:
            self._setup_employee_fields()

    def _setup_manager_fields(self):
        """Configure form for manager users."""
        # Managers can update status but not reason
        self.fields["status"].required = True
        self._make_field_readonly("reason")
        
        # Optionally make other fields readonly for managers
        readonly_fields = ["reg_status", "from_date", "to_date", "reg_duration"]
        for field_name in readonly_fields:
            if field_name in self.fields:
                self._make_field_readonly(field_name)

    def _setup_employee_fields(self):
        """Configure form for employee users."""
        # Employees must provide reason but cannot change status
        if "status" in self.fields:
            self.fields.pop("status")
        self.fields["reason"].required = True

    def _setup_initial_values(self):
        """Set initial values based on detected attendance events."""
        if not self.instance.pk:
            # Set initial values for new instances based on detected events
            if self.late_coming and not self.early_going:
                self._set_late_coming_defaults()
            elif self.early_going and not self.late_coming:
                self._set_early_going_defaults()

    def _set_late_coming_defaults(self):
        """Set default values for late coming scenario."""
        if self.late_coming:
            self.initial.update({
                "reg_status": settings.LATE_COMING,
                "from_date": self.late_coming.get("from_date"),
                "to_date": self.late_coming.get("to_date"),
                "reg_duration": self.late_coming.get("duration"),
            })

    def _set_early_going_defaults(self):
        """Set default values for early going scenario."""
        if self.early_going:
            self.initial.update({
                "reg_status": settings.EARLY_GOING,
                "from_date": self.early_going.get("from_date"),
                "to_date": self.early_going.get("to_date"), 
                "reg_duration": self.early_going.get("duration"),
            })

    def _make_field_readonly(self, field_name):
        """Make a specific field readonly with proper widget handling."""
        if field_name not in self.fields:
            return
            
        field = self.fields[field_name]
        widget = field.widget
        
        # Add readonly attribute
        widget.attrs["readonly"] = "readonly"
        
        # Handle specific widget types
        if isinstance(widget, forms.Textarea):
            # For textareas, disabled works better for styling
            widget.attrs["disabled"] = "disabled"
        elif isinstance(widget, forms.Select):
            # For selects, disabled is more appropriate
            widget.attrs["disabled"] = "disabled"
        elif isinstance(widget, forms.RadioSelect):
            # For radio buttons, disable all options
            widget.attrs["disabled"] = "disabled"

    def clean(self):
        """Custom validation for the form."""
        cleaned_data = super().clean()
        
        # Validate date range
        self._validate_date_range(cleaned_data)
        
        # Validate reg_status specific requirements
        self._validate_reg_status_requirements(cleaned_data)
        
        return cleaned_data

    def _validate_date_range(self, cleaned_data):
        """Validate that to_date is after from_date."""
        from_date = cleaned_data.get("from_date")
        to_date = cleaned_data.get("to_date")
        
        if from_date and to_date:
            if to_date <= from_date:
                raise forms.ValidationError(
                    _("End date must be after start date.")
                )
            
            # Validate duration is reasonable (e.g., not more than 24 hours)
            duration_hours = (to_date - from_date).total_seconds() / 3600
            if duration_hours > 24:
                raise forms.ValidationError(
                    _("Regularization duration cannot exceed 24 hours.")
                )

    def _validate_reg_status_requirements(self, cleaned_data):
        """Validate requirements based on regularization status."""
        reg_status = cleaned_data.get("reg_status")
        reason = cleaned_data.get("reason")
        
        # Ensure reason is provided for non-managers
        if not self.is_manager and not reason:
            raise forms.ValidationError(
                _("Reason is required for regularization requests.")
            )
        
        # Additional validation based on reg_status
        if reg_status == settings.MIS_PUNCHING:
            self._validate_mis_punching(cleaned_data)

    def _validate_mis_punching(self, cleaned_data):
        """Additional validation for mis punching scenarios."""
        # Add any specific validation for mis punching
        pass

    def save(self, commit=True):
        """Override save to handle additional processing."""
        instance = super().save(commit=False)
        
        # Calculate duration if from_date and to_date are provided
        if instance.from_date and instance.to_date:
            duration = instance.to_date - instance.from_date
            # Format duration as HH:MM
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            instance.reg_duration = f"{int(hours):02d}:{int(minutes):02d}"
        
        if commit:
            instance.save()
            
        return instance

    @property
    def available_events(self):
        """Return a summary of available events for this form."""
        return {
            'has_late_coming': bool(self.late_coming),
            'has_early_going': bool(self.early_going),
            'late_coming_duration': self.late_coming.get('duration') if self.late_coming else None,
            'early_going_duration': self.early_going.get('duration') if self.early_going else None,
        }

class LeaveStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = ["status"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["status"].widget = forms.Select(
            choices=self.get_filtered_choices(user)
        )

    def get_filtered_choices(self, user):
        current_status = self.instance
        all_choices = settings.LEAVE_STATUS_CHOICES

        if user is None:
            return all_choices

        is_applicant = user == current_status.appliedBy
        is_rm = hasattr(user, "employees") and user.employees.exists()
        is_lwp = current_status.leave_type.leave_type_short_code == "LWP"
        is_admin_dept = (
                user.personal_detail.designation.department.department == "admin"
        )
        # Case: Employee
        if is_applicant:
            if current_status.status in [settings.CANCELLED, settings.REJECTED]:
                return []  # No actions allowed
            return [
                (status, label)
                for status, label in all_choices
                if status == settings.PENDING_CANCELLATION
            ]
        if is_admin_dept and is_lwp:
            return [
                (status, label)
                for status, label in all_choices
                if status in [settings.APPROVED, settings.REJECTED]
            ]
        # Case: Reporting Manager
        if is_rm:
            if not is_admin_dept and is_lwp:
                return [
                    (status, label)
                    for status, label in all_choices
                    if status in [settings.RECOMMEND, settings.NOT_RECOMMEND]
                ]
            elif current_status.status == settings.PENDING_CANCELLATION:
                return [
                    (status, label)
                    for status, label in all_choices
                    if status == settings.CANCELLED
                ]

            else:
                return [
                    (status, label)
                    for status, label in all_choices
                    if status in [settings.APPROVED, settings.REJECTED]
                ]

        # Fallback to default
        return all_choices


class TourStatusUpdateForm(forms.ModelForm):
    reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": _("Enter your reason"),
            }
        ),
        label=_("Reason"),
        required=False,
    )

    class Meta:
        model = UserTour
        fields = ["status", "extended_end_date", "extended_end_time", "reason"]
        widgets = {
            "extended_end_date": DatePickerInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "extended_end_time": TimePickerInput(
                options={
                    "format": "hh:mm A",  # e.g., 02:30 PM
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={
                    "class": "form-control",
                },
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "reason": CKEditor5Widget(config_name="reason"),
        }
        labels = {
            "extended_end_date": _("New Date"),
            "extended_end_time": _("New Time"),
            "status": _("Select Tour Status"),
            "reason": _("Remark"),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        is_manager = kwargs.pop("is_manager", None)
        super().__init__(*args, **kwargs)
        current_status = self.instance

        if user is not None:
            if is_manager:
                self.fields.pop("extended_end_date", None)
                self.fields.pop("extended_end_time", None)
                filtered_choices = [
                    choice
                    for choice in settings.TOUR_STATUS_CHOICES
                    if choice[0]
                       in [settings.APPROVED, settings.REJECTED, settings.CANCELLED]
                ]
            else:
                if current_status.status in [settings.CANCELLED, settings.REJECTED]:
                    filtered_choices = [
                        choice
                        for choice in settings.TOUR_STATUS_CHOICES
                        if choice[0] == current_status.status
                    ]
                else:
                    filtered_choices = [
                        choice
                        for choice in settings.TOUR_STATUS_CHOICES
                        if choice[0]
                           in [
                               settings.EXTENDED,
                               settings.PENDING_CANCELLATION,
                           ]
                    ]
            self.fields["status"].widget = forms.Select(
                choices=filtered_choices,
                attrs={"class": "form-select"},
            )


class LeaveBalanceOpeningForm(forms.ModelForm):
    class Meta:
        model: LeaveBalanceOpenings
        field = [
            "user",
            "leave_type",
            "year",
            "no_of_leaves",
            "remaining_leave_balances",
        ]


class FilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=settings.LEAVE_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select", "id": "status-filter"}),
        required=False,
    )
    from_date = forms.DateField(
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            attrs={"class": "form-control"},
        ),
        required=False,
    )
    to_date = forms.DateField(
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            range_from="from_date",
            attrs={"class": "form-control"},
        ),
        required=False,
    )


class EmployeeChoicesForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={"data-role": "select", "id": "option"}),
        required=False,
        empty_label="Select a user",
    )


from django.contrib.auth.models import Permission, Group
from django.utils.translation import gettext_lazy as _


class CustomUserForm(forms.ModelForm):
    # Field for selecting permissions
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label="Permissions",
    )
    # Field for selecting groups
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label="Groups",
    )

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "official_email",
            "is_active",
            "is_rm",
            "reports_to",
            "device_location",
        ]
        labels = {
            "username": _("User Name"),
            "first_name": _("First Name"),
            "last_name": _("Last Name"),
            "email": _("Personal Email"),
            "official_email": _("Official Email"),
            "is_rm": _("Is Reporting Manager"),
            "reports_to": _("Select Manager (Reports To)"),
            "device_location": _("Employee Location"),
        }

        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("example12@#")}
            ),
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter First Name")}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter Last Name")}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": _("example@gmail.com")}
            ),
            "official_email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("example@companydomain.com"),
                }
            ),
            "is_rm": forms.CheckboxInput(
                attrs={
                    "type": "checkbox",
                    "class": "form-check-input",
                    "data-material": "true",
                }
            ),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            user.user_permissions.set(self.cleaned_data["permissions"])
            user.groups.set(self.cleaned_data["groups"])
        return user


class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = PersonalDetails
        fields = [
            "salutation",
            "avatar",
            "employee_code",
            "mobile_number",
            "alt_mobile_number",
            "official_mobile_number",
            "gender",
            "designation",
            "religion",
            "marital_status",
            "marriage_ann",
            "birthday",
            "doj",
            "dol",
            "dor",
            "dof",
        ]

        # Define custom labels with translations
        labels = {
            "employee_code": _("Employee Code"),
            "avatar": _("Avatar"),
            "mobile_number": _("Mobile Number"),
            "alt_mobile_number": _("Emergency Contact Number"),
            "gender": _("Gender"),
            "designation": _("Designation"),
            "official_mobile_number": _("Official Mobile Number"),
            "religion": _("Religion"),
            "marital_status": _("Marital Status"),
            "marriage_ann": _("Marriage Anniversary Date"),
            "birthday": _("Birthday"),
            "doj": _("Date of Joining"),
            "dol": _("Date of Leaving"),
            "dor": _("Date of Resignation"),
            "dof": _("Date of Final Settlement"),
        }

        # Define widgets with placeholders
        widgets = {
            "avatar": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "type": "file",
                    "data-role": "file",
                    "data-mode": "drop",
                }
            ),
            "employee_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-role": "input",
                    "placeholder": _("Enter Employee Code"),
                }
            ),
            "mobile_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-role": "input, input-mask",
                    "data-mask": "+91 _____-_____",
                    "placeholder": _("Enter Mobile Number"),
                }
            ),
            "alt_mobile_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-role": "input,input-mask",
                    "data-mask": "+91 _____-_____",
                    "placeholder": _("Enter Alternate Mobile Number"),
                }
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "designation": forms.Select(attrs={"class": "form-control"}),
            "official_mobile_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-role": "input,input-mask",
                    "data-mask": "+91 _____-_____",
                    "placeholder": _("Enter Official Mobile Number"),
                }
            ),
            "religion": forms.Select(
                attrs={"class": "form-control", "data-role": "select"}
            ),
            "marital_status": forms.Select(attrs={"class": "form-control"}),
            "ctc": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-role": "input",
                    "placeholder": _("Enter CTC"),
                }
            ),
            "birthday": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "marriage_ann": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "doj": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "dol": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "dor": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "dof": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar and self.instance.pk:
            return self.instance.avatar
        return avatar


class EmployeePersonalDetailForm(forms.ModelForm):
    class Meta:
        model = PersonalDetails
        fields = [
            "avatar",
            "mobile_number",
            "alt_mobile_number",
            "official_mobile_number",
            "gender",
            "designation",
            "religion",
            "marital_status",
            "marriage_ann",
        ]

        labels = {
            "avatar": _("Avatar"),
            "mobile_number": _("Mobile Number"),
            "alt_mobile_number": _("Emergency Contact Number"),
            "gender": _("Gender"),
            "designation": _("Designation"),
            "official_mobile_number": _("Official Mobile Number"),
            "religion": _("Religion"),
            "marital_status": _("Marital Status"),
            "marriage_ann": _("Marriage Anniversary Date"),
        }

        widgets = {
            "avatar": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "type": "file",
                    "data-role": "file",
                    "data-mode": "drop",
                }
            ),
            "mobile_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter Mobile Number")}
            ),
            "alt_mobile_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter Emergency Contact Number"),
                }
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "designation": forms.Select(attrs={"class": "form-control"}),
            "official_mobile_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter Official Mobile Number"),
                }
            ),
            "religion": forms.Select(
                attrs={"class": "form-control", "data-role": "select"}
            ),
            "marital_status": forms.Select(attrs={"class": "form-control"}),
            "marriage_ann": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This makes the avatar field optional even if it's required on the model
        self.fields["avatar"].required = False

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar and self.instance.pk:
            return self.instance.avatar
        return avatar


class PermanentAddressForm(forms.ModelForm):
    class Meta:
        model = PermanentAddress
        fields = [
            "address_line_1",
            "address_line_2",
            "country",
            "district",
            "state",
            "zipcode",
            "is_active",
        ]

        # Custom labels
        labels = {
            "address_line_1": _("Address Line 1"),
            "address_line_2": _("Address Line 2"),
            "country": _("Country"),
            "district": _("District"),
            "state": _("State"),
            "zipcode": _("ZIP Code"),
            "is_active": _("Is Active"),
        }

        # Define widgets with placeholders
        widgets = {
            "address_line_1": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter Address Line 1"),
                }
            ),
            "address_line_2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter Address Line 2"),
                }
            ),
            "country": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter Country")}
            ),
            "district": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter District")}
            ),
            "state": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter State")}
            ),
            "zipcode": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter ZIP Code")}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

        validators = {
            "zipcode": RegexValidator(
                r"^\d{5}(?:[-\s]\d{4})?$", _("Enter a valid ZIP code")
            ),
        }


class CorrespondingAddressForm(forms.ModelForm):
    class Meta:
        model = CorrespondingAddress
        fields = [
            "address_line_1",
            "address_line_2",
            "country",
            "district",
            "state",
            "zipcode",
        ]

        # Custom labels
        labels = {
            "user": _("Employee"),
            "address_line_1": _("Address Line 1"),
            "address_line_2": _("Address Line 2"),
            "country": _("Country"),
            "district": _("District"),
            "state": _("State"),
            "zipcode": _("ZIP Code"),
        }

        # Define widgets with placeholders
        widgets = {
            "address_line_1": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter Address Line 1"),
                }
            ),
            "address_line_2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter Address Line 2"),
                }
            ),
            "country": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter Country")}
            ),
            "district": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter District")}
            ),
            "state": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter State")}
            ),
            "zipcode": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Enter ZIP Code")}
            ),
        }

        # Define validations
        validators = {
            "zipcode": RegexValidator(
                r"^\d{5}(?:[-\s]\d{4})?$", _("Enter a valid ZIP code")
            ),
        }


class AttendanceReportFilterForm(forms.Form):
    # Define the form fields
    location = forms.ModelMultipleChoiceField(
        queryset=OfficeLocation.objects.all(),
        required=True,
        widget=forms.SelectMultiple(),
        label="Location",
    )
    from_date = forms.DateField(
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            attrs={"class": "form-control"},
        ),
        required=False,
    )
    to_date = forms.DateField(
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            range_from="from_date",
            attrs={"class": "form-control"},
        ),
        required=False,
    )

    active = forms.BooleanField(
        required=False,
        label="Active Employees Only",
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )


class LeaveReportFilterForm(forms.Form):
    location = forms.ModelMultipleChoiceField(
        queryset=OfficeLocation.objects.all(),
        required=False,
        widget=forms.SelectMultiple(),
        label="Location",
    )
    year = forms.DateField(
        widget=DatePickerInput(
            options={
                "format": "YYYY",
                "viewMode": "years",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            attrs={"class": "form-control"},
        ),
        required=False,
    )
    active = forms.BooleanField(
        required=False,
        label="Active Employees Only",
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )


class AttendanceLogActionForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4, "cols": 40}),
        required=False,
        label="Remark",
    )


class PopulateAttendanceForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label=_("User"),
        required=False,
        help_text=_("Select a specific user or leave blank to process all users."),
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    from_date = forms.DateTimeField(
        label=_("From Date"),
        required=True,
        widget=DateTimePickerInput(
            options={
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            attrs={"class": "form-control"},
        ),
    )
    to_date = forms.DateTimeField(
        label=_("To Date"),
        required=True,
        widget=DateTimePickerInput(
            options={
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            range_from="from_date",
            attrs={"class": "form-control"},
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get("from_date")
        to_date = cleaned_data.get("to_date")

        # Validation: Ensure `from_date` is not greater than `to_date`
        if from_date and to_date and from_date > to_date:
            raise forms.ValidationError(
                _("The from-date cannot be later than the to-date.")
            )

        return cleaned_data


class LeaveTransactionForm(forms.Form):
    leave_balance = forms.ChoiceField(
        required=False,
        label=_("Leave Balance"),
        choices=[],  # To be dynamically populated in the form initialization
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text=_("The leave balance associated with this transaction."),
    )
    leave_type = forms.ChoiceField(
        required=False,
        label=_("Leave Type"),
        choices=[],  # To be dynamically populated in the form initialization
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text=_("The type of leave being requested (e.g., sick leave, vacation)."),
    )
    no_of_days_approved = forms.FloatField(
        required=True,
        label=_("Number of Days Approved"),
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text=_("Number of leave days that have been approved."),
    )
    transaction_type = forms.ChoiceField(
        required=True,
        label=_("Transaction Type"),
        choices=[("add", _("Add")), ("subtract", _("Subtract"))],
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text=_("The type of transaction (add or subtract leaves)."),
    )
    remarks = forms.CharField(
        required=False,
        label=_("Remarks"),
        widget=forms.Textarea(attrs={"class": "form-control"}),
        help_text=_("Any additional remarks regarding the leave transaction."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["leave_balance"].choices = self.get_leave_balance_choices()
        self.fields["leave_type"].choices = self.get_leave_type_choices()

    def get_leave_balance_choices(self):
        # Replace with actual queryset to populate choices
        leave_balances = LeaveBalanceOpenings.objects.filter(year=timezone.now().year)
        return [("", _("Select Leave Balance"))] + [
            (lb.pk, str(lb)) for lb in leave_balances
        ]

    def get_leave_type_choices(self):
        # Replace with actual queryset to populate choices
        leave_types = LeaveType.objects.all()
        return [("", _("Select Leave Type"))] + [
            (lt.pk, lt.leave_type) for lt in leave_types
        ]

    def clean(self):
        cleaned_data = super().clean()
        leave_balance = cleaned_data.get("leave_balance")
        leave_type = cleaned_data.get("leave_type")

        # Ensure only one of leave_balance or leave_type is selected
        if leave_balance and leave_type:
            raise forms.ValidationError(
                "You can select only one of 'Leave Balance' or 'Leave Type', not both."
            )

        if not leave_balance and not leave_type:
            raise forms.ValidationError(
                "You must select at least one of 'Leave Balance' or 'Leave Type'."
            )

        return cleaned_data

    def process(self):
        """
        Handles form processing to create LeaveTransaction instances.
        """
        cleaned_data = self.cleaned_data
        leave_balance_id = cleaned_data.get("leave_balance")
        leave_type = cleaned_data.get("leave_type")
        no_of_days_approved = cleaned_data.get("no_of_days_approved")
        transaction_type = cleaned_data.get("transaction_type")
        remarks = cleaned_data.get("remarks")

        if leave_balance_id:
            leave_balance = LeaveBalanceOpenings.objects.get(id=leave_balance_id)
            transaction = LeaveTransaction(
                leave_balance=leave_balance,
                leave_type=leave_balance.leave_type,  # Assuming leave type is linked to leave balance
                transaction_date=timezone.now(),
                no_of_days_approved=no_of_days_approved,
                transaction_type=transaction_type,
                remarks=remarks,
            )
            transaction.save()
            transaction.apply_transaction()

        elif leave_type:
            leave_balances = LeaveBalanceOpenings.objects.filter(
                leave_type=leave_type, year=timezone.now().year
            )
            for leave_balance in leave_balances:
                transaction = LeaveTransaction(
                    leave_balance=leave_balance,
                    leave_type_id=leave_type,
                    transaction_date=timezone.now(),
                    no_of_days_approved=no_of_days_approved,
                    transaction_type=transaction_type,
                    remarks=remarks,
                )
                transaction.save()
                transaction.apply_transaction()
        else:
            raise ValueError("Either leave_balance or leave_type must be provided.")


from PIL import Image


class AvatarUpdateForm(forms.ModelForm):
    class Meta:
        model = PersonalDetails
        fields = ["avatar"]
        widgets = {
            "avatar": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "type": "file",
                    "data-role": "file",
                    "data-mode": "drop",
                }
            ),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            try:
                # Open the image file using PIL (Pillow)
                image = Image.open(avatar)
                # Check if the image is square
                if image.width != image.height:
                    raise ValidationError(
                        "The avatar must be a square image (equal width and height)."
                    )

                # Check minimum size requirement
                # if image.width < 512 or image.height < 512:
                #     raise ValidationError("The avatar must be at least 512x512 pixels.")

            except Exception:
                raise ValidationError(
                    "Invalid image file. Please upload a valid image."
                )
        return avatar


class LeaveBalanceForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label=_("User"),
        help_text=_(
            "Select a user to update their leave balance. Leave blank to update all users."
        ),
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": _("Select a user"),
            }
        ),
    )
    leave_type = forms.ModelChoiceField(
        queryset=LeaveType.objects.all(),
        required=True,
        label=_("Leave Type"),
        help_text=_("The type of leave to update or create balances for."),
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": _("Select a leave type"),
            }
        ),
    )
    year = forms.IntegerField(
        required=True,
        label=_("Year"),
        help_text=_("The year for which the leave balance is applicable."),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter year"),
            }
        ),
    )
    opening_balance = forms.FloatField(
        required=False,
        label=_("Opening Balance"),
        help_text=_("Enter the opening balance for the leave."),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter opening balance"),
            }
        ),
    )
    closing_balance = forms.FloatField(
        required=False,
        label=_("Closing Balance"),
        help_text=_("Enter the closing balance for the leave."),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter closing balance"),
            }
        ),
    )
    no_of_leaves = forms.FloatField(
        required=False,
        label=_("Number of Leaves"),
        help_text=_(
            "The total number of leaves allocated to the user for this leave type."
        ),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter number of leaves"),
            }
        ),
    )
    remaining_leave_balances = forms.FloatField(
        required=False,
        label=_("Remaining Leave Balance"),
        help_text=_(
            "The remaining balance of leaves available to the user for this leave type."
        ),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter remaining leave balance"),
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        opening_balance = cleaned_data.get("opening_balance")
        closing_balance = cleaned_data.get("closing_balance")
        no_of_leaves = cleaned_data.get("no_of_leaves")
        remaining_leave_balances = cleaned_data.get("remaining_leave_balances")

        # Ensure at least one balance field is provided
        if not any(
                [opening_balance, closing_balance, no_of_leaves, remaining_leave_balances]
        ):
            raise forms.ValidationError(
                _(
                    "At least one balance field (Opening Balance, Closing Balance, Number of Leaves, or Remaining Leave Balance) must be provided."
                )
            )
        return cleaned_data


from django import forms


class HRAnnouncementAdminForm(forms.ModelForm):
    class Meta:
        model = HRAnnouncement
        fields = [
            "title",
            "type",
            "start_date",
            "end_date",
            "is_active",
            "pinned",
            "audience_roles",
            "content",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control"},
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                    "type": "checkbox",
                }
            ),
            "pinned": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                    "type": "checkbox",
                }
            ),
            "start_date": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "end_date": DatePickerInput(
                options={
                    "format": "DD MMM, YYYY",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                range_from="start_date",
                attrs={"class": "form-control"},
            ),
            "to_destination": forms.TextInput(
                attrs={"class": "form-control"},
            ),
            "content": CKEditor5Widget(config_name="extends"),
        }
        labels = {
            "title": _("Title"),
            "start_date": _("Start Date"),
            "end_date": _("End Date"),
            "content": _("Content"),
            "pinned": _("Pinned"),
        }


class AttendanceAggregationForm(forms.Form):
    start_date = forms.DateField(
        label=_("From Date"),
        required=True,
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            attrs={"class": "form-control"},
        ),
    )
    end_date = forms.DateField(
        label=_("To Date"),
        required=True,
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            range_from="from_date",
            attrs={"class": "form-control"},
        ),
    )


class MonthRangeForm(forms.Form):
    start_month = forms.DateField(
        label=_("From Month"),
        required=False,
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            attrs={"class": "form-control"},
        ),
    )
    end_month = forms.DateField(
        label=_("To Month"),
        required=False,
        widget=DatePickerInput(
            options={
                "format": "DD MMM, YYYY",
                "showClear": True,
                "showClose": True,
                "useCurrent": False,
            },
            range_from="start_month",
            attrs={"class": "form-control"},
        ),
    )


class BulkAttendanceForm(forms.Form):
    """
    Form for bulk attendance marking
    """
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'required': True
        }),
        label='Start Date',
        initial=timezone.now().date(),
        help_text='Select the start date for attendance'
    )

    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'required': True
        }),
        label='End Date',
        initial=timezone.now().date(),
        help_text='Select the end date for attendance'
    )

    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control',
            'required': True
        }),
        label='Start Time',
        initial='09:30',
        help_text='Select the start time for attendance'
    )

    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control',
            'required': True
        }),
        label='End Time',
        initial='17:30',
        help_text='Select the end time for attendance'
    )

    employees = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'multiple': True,
            'data-placeholder': 'Choose employees...'
        }),
        label='Select Employees',
        required=False,
        help_text='Select specific employees (leave empty if selecting all)'
    )

    select_all = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Select All Employees',
        required=False,
        help_text='Check to select all active employees'
    )

    title_prefix = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bulk Attendance'
        }),
        label='Title Prefix',
        initial='Bulk Attendance',
        help_text='Prefix for attendance log titles'
    )

    reason = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bulk attendance marking'
        }),
        label='Reason',
        initial='Bulk attendance marking',
        help_text='Reason for marking attendance'
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        employees = cleaned_data.get('employees')
        select_all = cleaned_data.get('select_all')

        # Validate date range
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('End date must be after or equal to start date.')

        # Validate datetime combination
        if start_date and end_date and start_time and end_time:
            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)

            if start_datetime >= end_datetime:
                raise ValidationError('End date/time must be after start date/time.')

            # Check if duration is reasonable (not more than 24 hours per day)
            duration = end_datetime - start_datetime
            max_duration = timedelta(days=(end_date - start_date).days + 1)

            if duration > max_duration:
                raise ValidationError('Duration cannot exceed 24 hours per day.')

        # Validate employee selection
        if not select_all and not employees:
            raise ValidationError('Please select at least one employee or check "Select All".')

        # Validate future dates (optional - remove if you want to allow future dates)
        today = timezone.now().date()
        if start_date and start_date > today:
            raise ValidationError('Start date cannot be in the future.')

        return cleaned_data

    def get_selected_employees(self):
        """
        Returns the selected employees based on form data
        """
        if self.cleaned_data.get('select_all'):
            return User.objects.filter(is_active=True)
        else:
            return self.cleaned_data.get('employees', User.objects.none())

    def get_duration(self):
        """
        Calculate and return the duration between start and end datetime
        """
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        start_time = self.cleaned_data.get('start_time')
        end_time = self.cleaned_data.get('end_time')

        if all([start_date, end_date, start_time, end_time]):
            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)
            return end_datetime - start_datetime

        return timedelta(0)

    def get_duration_as_time(self):
        """
        Return duration as time object for storing in TimeField
        """
        duration = self.get_duration()
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        # Cap at 23:59 for TimeField compatibility
        if hours >= 24:
            hours = 23
            minutes = 59

        return datetime.min.time().replace(hour=hours, minute=minutes)
