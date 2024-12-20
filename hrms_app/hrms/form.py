from hrms_app.models import *
import unicodedata
from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import capfirst
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget
from colorfield.widgets import ColorWidget
from hrms_app.hrms.utils import is_holiday, is_weekend
from hrms_app.utility.leave_utils import apply_leave_policies, check_overlapping_leaves
from django.core.validators import RegexValidator
from bootstrap_datepicker_plus.widgets import (
    DatePickerInput,
    TimePickerInput,
    DateTimePickerInput,
    MonthPickerInput,
    YearPickerInput,
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
        email_field_name = User.get_email_field_name()
        active_users = User._default_manager.filter(
            **{
                "%s__iexact" % email_field_name: email,
                "is_active": True,
            }
        )
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
        email_field_name = User.get_email_field_name()
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
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
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


class TourForm(forms.ModelForm):
    approval_type = forms.ChoiceField(
        choices=settings.APPROVAL_TYPE_CHOICES,
        widget=forms.Select(),
        label=_("Approval Type"),
        required=True,
    )

    class Meta:
        model = UserTour
        fields = [
            "approval_type",
            "from_destination",
            "start_date",
            "start_time",
            "to_destination",
            "end_date",
            "end_time",
            "remarks",
        ]
        widgets = {
            "from_destination": forms.TextInput(
                attrs={"class": "form-control"},
            ),
            "start_date": DatePickerInput(
                options={
                    "format": "YYYY-MM-DD",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                attrs={"class": "form-control"},
            ),
            "start_time": TimePickerInput(
                attrs={"class": "form-control"},
            ),
            "end_date": DatePickerInput(
                options={
                    "format": "YYYY-MM-DD",
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                range_from="start_date",
                attrs={"class": "form-control"},
            ),
            "end_time": TimePickerInput(
                attrs={"class": "form-control"},
            ),
            "to_destination": forms.TextInput(
                attrs={"class": "form-control"},
            ),
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
        super(TourForm, self).__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.required = True


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


class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = [
            "leave_type",
            "startDate",
            "endDate",
            "startDayChoice",
            "endDayChoice",
            "usedLeave",
            "balanceLeave",
            "reason",
        ]
        widgets = {
            "startDate": forms.TextInput(
                attrs={"class": "form-control datepicker"},
            ),
            "endDate": forms.TextInput(
                attrs={"class": "form-control datepicker"},
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
            "balanceLeave": forms.TextInput(
                attrs={"type": "text", "data-role": "input", "readonly": "readonly"}
            ),
            "reason": CKEditor5Widget(attrs={"class": "django_ckeditor_5"}),
        }
        labels = {
            "startDate": _("Start Date"),
            "endDate": _("End Date"),
            "usedLeave": _("Currently Booked"),
            "balanceLeave": _("Available Balance"),
            "reason": _("Reason"),
            "startDayChoice": _("Start Day"),
            "endDayChoice": _("End Day"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        leave_type = kwargs.pop("leave_type", None)
        super(LeaveApplicationForm, self).__init__(*args, **kwargs)
        if self.user:
            leave_balance = LeaveBalanceOpenings.objects.filter(
                user=self.user, leave_type_id=leave_type
            ).first()
            if leave_balance:
                self.fields["balanceLeave"].initial = (
                    leave_balance.remaining_leave_balances
                )

        self.fields["leave_type"].initial = leave_type

    def clean(self):
        cleaned_data = super().clean()
        startDate = cleaned_data.get("startDate")
        endDate = cleaned_data.get("endDate")
        usedLeave = cleaned_data.get("usedLeave")
        leaveTypeId = cleaned_data.get("leave_type")

        if not startDate or not endDate:
            raise ValidationError(_("Start Date and End Date are required."))

        if startDate > endDate:
            raise ValidationError(_("End Date must be after Start Date."))

        current_date = startDate
        while current_date <= endDate:
            if leaveTypeId.leave_type_short_code == "CL" and (
                is_weekend(current_date) or is_holiday(current_date)
            ):
                usedLeave -= 1
            current_date += timedelta(days=1)

        cleaned_data["usedLeave"] = usedLeave

        apply_leave_policies(self.user, leaveTypeId, startDate, endDate, usedLeave)

        # Check for overlapping leave applications
        if check_overlapping_leaves(self.user, startDate, endDate):
            self.add_error(None, _("You have overlapping leave applications."))

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
        widget=forms.TextInput(attrs={'placeholder': 'Search by title or user', "class": "form-control"})
    )

    class Meta:
        model = AttendanceLog
        fields = ("reg_status", "status", "is_submitted","is_regularisation")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_submitted'].initial = True

class AttendanceLogForm(forms.ModelForm):

    class Meta:
        model = AttendanceLog
        fields = [
            "reg_status",
            "status",
            "start_date",
            "end_date",
            "duration",
            "from_date",
            "to_date",
            "reg_duration",
            "reason",
        ]
        widgets = {
            "reg_status": forms.Select(attrs={"class": "form-control"}),
            "duration": TimePickerInput(attrs={"class": "form-control","readonly": "readonly"}),
            "reg_duration": forms.TextInput(attrs={"class": "form-control","readonly": "readonly"}),
            "start_date": DateTimePickerInput(
                options={
                    "showClear": True,
                    "showClose": True,
                    "useCurrent": False,
                },
                format="%Y-%m-%d %H:%M",
                attrs={"class": "form-control ","readonly": "readonly"},
            ),
            "end_date": DateTimePickerInput(
                range_from="start_date",
                format="%Y-%m-%d %H:%M",
                attrs={"class": "form-control","readonly": "readonly"},
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
            "reason": forms.Textarea(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.is_manager = kwargs.pop("is_manager", False)
        super(AttendanceLogForm, self).__init__(*args, **kwargs)

        if not self.is_manager:
            # Employee: render only the reason field and make it editable
            self.fields.pop("status", None)
            self.fields["reason"].required = True

        else:
            # Manager: make reason read-only and status editable
            self.fields["status"].required = True
            self.make_field_readonly("reason")

    def make_field_readonly(self, field_name):
        """Set a specific field to readonly by updating its widget attributes."""
        if field_name in self.fields:
            self.fields[field_name].widget.attrs["readonly"] = "readonly"

            # For Textarea, use disabled because `readonly` doesn't always work with styling.
            if isinstance(self.fields[field_name].widget, forms.Textarea):
                self.fields[field_name].widget.attrs["disabled"] = "disabled"


class LeaveStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = ["status"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            current_status = self.instance
            if user.is_rm and user != current_status.appliedBy:
                filtered_choices = [
                    choice
                    for choice in settings.LEAVE_STATUS_CHOICES
                    if choice[0]
                    in [settings.APPROVED, settings.REJECTED, settings.CANCELLED]
                ]
            elif user == current_status.appliedBy:  # Employee
                if current_status.status == settings.CANCELLED:
                    filtered_choices = [
                        choice
                        for choice in settings.LEAVE_STATUS_CHOICES
                        if choice[0] == settings.CANCELLED
                    ]
                else:
                    filtered_choices = [
                        choice
                        for choice in settings.LEAVE_STATUS_CHOICES
                        if choice[0] == settings.PENDING_CANCELLATION
                    ]
            self.fields["status"].widget = forms.Select(choices=filtered_choices)


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
                attrs={
                    "class": "form-control",
                }
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
                            settings.COMPLETED,
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
                "format": "YYYY-MM-DD",
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
                "format": "YYYY-MM-DD",
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
        widget=forms.SelectMultiple(attrs={"data-role": "select"}),
        label="Permissions",
    )
    # Field for selecting groups
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"data-role": "select"}),
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
            "is_rm",
            "reports_to",
        ]
        labels = {
            "username": _("User Name"),
            "first_name": _("First Name"),
            "last_name": _("Last Name"),
            "email": _("Personal Email"),
            "official_email": _("Official Email"),
            "is_rm": _("Is Reporting Manager"),
            "reports_to": _("Select Manager (Reports To)"),
        }

        widgets = {
            "username": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("example12@#")}
            ),
            "first_name": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter First Name")}
            ),
            "last_name": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter Last Name")}
            ),
            "email": forms.EmailInput(
                attrs={"data-role": "input", "placeholder": _("example@gmail.com")}
            ),
            "official_email": forms.EmailInput(
                attrs={
                    "data-role": "input",
                    "placeholder": _("example@companydomain.com"),
                }
            ),
            "reports_to": forms.Select(attrs={"data-role": "select"}),
            "is_rm": forms.CheckboxInput(
                attrs={
                    "type": "checkbox",
                    "data-role": "switch",
                    "data-material": "true",
                }
            ),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Set permissions for the user
            user.user_permissions.set(self.cleaned_data["permissions"])
            # Set groups for the user
            user.groups.set(self.cleaned_data["groups"])
        return user


class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = PersonalDetails
        fields = [
            "avatar",
            "employee_code",
            "mobile_number",
            "alt_mobile_number",
            "official_mobile_number",
            "gender",
            "designation",
            "religion",
            "marital_status",
            "ctc",
            "birthday",
            "ann_date",
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
            "alt_mobile_number": _("Alternate Mobile Number"),
            "gender": _("Gender"),
            "designation": _("Designation"),
            "official_mobile_number": _("Official Mobile Number"),
            "religion": _("Religion"),
            "marital_status": _("Marital Status"),
            "birthday": _("Birthday"),
            "ctc": _("CTC"),
            "ann_date": _("Anniversary Date"),
            "doj": _("Date of Joining"),
            "dol": _("Date of Leaving"),
            "dor": _("Date of Resignation"),
            "dof": _("Date of Final Settlement"),
        }

        # Define widgets with placeholders
        widgets = {
            "avatar": forms.FileInput(
                attrs={"type": "file", "data-role": "file", "data-mode": "drop"}
            ),
            "employee_code": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter Employee Code")}
            ),
            "mobile_number": forms.TextInput(
                attrs={
                    "data-role": "input, input-mask",
                    "data-mask": "+91 _____-_____",
                    "placeholder": _("Enter Mobile Number"),
                }
            ),
            "alt_mobile_number": forms.TextInput(
                attrs={
                    "data-role": "input,input-mask",
                    "data-mask": "+91 _____-_____",
                    "placeholder": _("Enter Alternate Mobile Number"),
                }
            ),
            "gender": forms.Select(attrs={"data-role": "select"}),
            "designation": forms.Select(attrs={"data-role": "select"}),
            "official_mobile_number": forms.TextInput(
                attrs={
                    "data-role": "input,input-mask",
                    "data-mask": "+91 _____-_____",
                    "placeholder": _("Enter Official Mobile Number"),
                }
            ),
            "religion": forms.Select(attrs={"data-role": "select"}),
            "marital_status": forms.Select(attrs={"data-role": "select"}),
            "ctc": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter CTC")}
            ),
            "birthday": forms.DateInput(
                attrs={
                    "data-role": "calendarpicker",
                    "placeholder": _("Select Birthday"),
                }
            ),
            "ann_date": forms.DateInput(
                attrs={
                    "data-role": "calendarpicker",
                    "placeholder": _("Select Anniversary Date"),
                }
            ),
            "doj": forms.DateInput(
                attrs={
                    "data-role": "calendarpicker",
                    "placeholder": _("Select Date of Joining"),
                }
            ),
            "dol": forms.DateInput(
                attrs={
                    "data-role": "calendarpicker",
                    "placeholder": _("Select Date of Leaving"),
                }
            ),
            "dor": forms.DateInput(
                attrs={
                    "data-role": "calendarpicker",
                    "placeholder": _("Select Date of Resignation"),
                }
            ),
            "dof": forms.DateInput(
                attrs={
                    "data-role": "calendarpicker",
                    "placeholder": _("Select Date of Final Settlement"),
                }
            ),
        }


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
                attrs={"data-role": "input", "placeholder": _("Enter Address Line 1")}
            ),
            "address_line_2": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter Address Line 2")}
            ),
            "country": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter Country")}
            ),
            "district": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter District")}
            ),
            "state": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter State")}
            ),
            "zipcode": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter ZIP Code")}
            ),
            "is_active": forms.CheckboxInput(attrs={"data-role": "checkbox"}),
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
                attrs={"data-role": "input", "placeholder": _("Enter Address Line 1")}
            ),
            "address_line_2": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter Address Line 2")}
            ),
            "country": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter Country")}
            ),
            "district": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter District")}
            ),
            "state": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter State")}
            ),
            "zipcode": forms.TextInput(
                attrs={"data-role": "input", "placeholder": _("Enter ZIP Code")}
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
                "format": "YYYY-MM-DD",
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
                "format": "YYYY-MM-DD",
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
        widget=forms.CheckboxInput(attrs={"data-role": "checkbox"}),
    )

    detailed = forms.BooleanField(
        required=False,
        label="Detailed Reports Only",
        initial=False,
        widget=forms.CheckboxInput(attrs={"data-role": "checkbox"}),
    )
