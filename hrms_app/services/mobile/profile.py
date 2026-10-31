"""
The employee's own profile for the mobile Profile tab.

Editing goes through the web's forms, so the rules stay the same:
- personal details -> EmployeePersonalDetailForm, except the official mobile
                      number and designation (admin / superuser only)
- addresses        -> PermanentAddressForm / CorrespondingAddressForm
- photo            -> AvatarUpdateForm (must be square, so it is cropped here)
- password         -> ChangeUserPasswordForm

Every field an employee changes is emailed to HR with its old and new value.
"""
import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.forms.models import model_to_dict

from hrms_app.hrms.form import (
    AvatarUpdateForm,
    ChangeUserPasswordForm,
    CorrespondingAddressForm,
    EmployeePersonalDetailForm,
    PermanentAddressForm,
)
from hrms_app.models import CorrespondingAddress, Gender, MaritalStatus, PermanentAddress, Religion
from hrms_app.services.mobile.formatters import employee_code_label, iso_date, shift_payload
from hrms_app.services.mobile.my_leaves import _person
from hrms_app.tasks import send_personal_detail_update_email

logger = logging.getLogger(__name__)

EDIT_PERMISSION = "hrms_app.change_personaldetails"
MARRIED = "married"
MAX_AVATAR_BYTES = 8 * 1024 * 1024
AVATAR_SIDE = 800
ADDRESS_FIELDS = ("address_line_1", "address_line_2", "country", "district", "state", "zipcode")
DETAIL_FIELDS = (
    "mobile_number",
    "alt_mobile_number",
    "gender",
    "religion",
    "marital_status",
    "marriage_ann",
)
ADDRESSES = {
    "permanent": ("Permanent Address", PermanentAddress, PermanentAddressForm, "permanent_addresses"),
    "correspondence": ("Correspondence Address", CorrespondingAddress, CorrespondingAddressForm, "corres_addresses"),
}


def _choice(item, label):
    return {"id": item.pk, "label": label} if item else None


def _address_payload(address):
    return {name: getattr(address, name, None) or "" for name in ADDRESS_FIELDS} if address else None


def _options():
    return {
        "genders": [_choice(g, g.gender) for g in Gender.objects.filter(is_active=True).order_by("gender")],
        "religions": [_choice(r, r.religion) for r in Religion.objects.filter(is_active=True).order_by("religion")],
        "marital_statuses": [
            _choice(m, m.marital_status)
            for m in MaritalStatus.objects.filter(is_active=True).order_by("marital_status")
        ],
    }


def get_profile(user, build_url):
    details = getattr(user, "personal_detail", None)
    designation = getattr(details, "designation", None)
    avatar = getattr(details, "avatar", None)
    return {
        "name": user.get_full_name() or user.username,
        "salutation": getattr(details, "salutation", None),
        "employee_code": employee_code_label(getattr(details, "employee_code", None) or user.username),
        "avatar_url": build_url(avatar.url) if avatar else None,
        "designation": _choice(designation, getattr(designation, "designation", None)),
        "department": str(designation.department) if designation and designation.department_id else None,
        "date_of_joining": iso_date(getattr(details, "doj", None)),
        "reports_to": _person(user.reports_to),
        "shift": shift_payload(user),
        "official_email": user.official_email or None,
        "email": user.email or None,
        "mobile_number": getattr(details, "mobile_number", None),
        "alt_mobile_number": getattr(details, "alt_mobile_number", None),
        "official_mobile_number": getattr(details, "official_mobile_number", None),
        "cug_mobile_number": getattr(details, "cug_mobile_number", None),
        "birthday": iso_date(getattr(details, "birthday", None)),
        "marriage_anniversary": iso_date(getattr(details, "marriage_ann", None)),
        "gender": _choice(getattr(details, "gender", None), str(getattr(details, "gender", ""))),
        "religion": _choice(getattr(details, "religion", None), str(getattr(details, "religion", ""))),
        "marital_status": _choice(
            getattr(details, "marital_status", None), str(getattr(details, "marital_status", ""))
        ),
        "permanent_address": _address_payload(user.permanent_addresses.last()),
        "correspondence_address": _address_payload(user.corres_addresses.last()),
        "can_edit_details": user.has_perm(EDIT_PERMISSION),
        "options": _options(),
    }


def _text(value):
    return "" if value is None else str(value)


def _changes(form, before, prefix=""):
    """{label: (old, new)} as plain text, ready for the HR email task."""
    changes = {}
    for name in form.changed_data:
        old = _text(before.get(name))
        new = _text(form.cleaned_data.get(name))
        if old != new:
            changes[f"{prefix}{form.fields[name].label or name}"] = (old, new)
    return changes


def _email_hr(user, changes):
    if not changes:
        return

    def enqueue():
        try:
            send_personal_detail_update_email.delay(
                user_full_name=user.get_full_name(),
                username=user.username,
                changed_fields=changes,
            )
        except Exception:  # a mail outage must not undo a saved change
            logger.exception("Could not queue the HR email for %s", user.pk)

    transaction.on_commit(enqueue)


def _form_errors(form):
    return {name: [str(error) for error in messages] for name, messages in form.errors.items()}


def _is_married(status_id):
    if not str(status_id).isdigit():
        return False
    return MaritalStatus.objects.filter(pk=status_id, marital_status__iexact=MARRIED).exists()


def update_details(user, data):
    """Same fields as the web's Update Personal Detail form. Returns errors or None."""
    details = user.personal_detail
    # Read before validating: the form writes into the instance.
    before = {name: getattr(details, name, None) for name in DETAIL_FIELDS}
    fields = {name: data.get(name) or "" for name in DETAIL_FIELDS}
    # Only admin / superuser change these. The form requires them, so it gets
    # the stored values and anything the client sends is ignored.
    fields["official_mobile_number"] = details.official_mobile_number
    fields["designation"] = details.designation_id
    if _is_married(fields["marital_status"]):
        if not fields["marriage_ann"]:
            return {"marriage_ann": ["Select your marriage anniversary date."]}
    else:
        fields["marriage_ann"] = ""
    form = EmployeePersonalDetailForm(fields, instance=details)
    if not form.is_valid():
        return _form_errors(form)
    changes = _changes(form, before)
    with transaction.atomic():
        form.save()
        _email_hr(user, changes)
    return None


def update_address(user, kind, data):
    """Saves straight away, as on the web. Returns errors or None."""
    title, model, form_class, related = ADDRESSES[kind]
    address = getattr(user, related).last()
    before = model_to_dict(address, fields=ADDRESS_FIELDS) if address else {}
    fields = {name: str(data.get(name) or "").strip() for name in ADDRESS_FIELDS}
    # The permanent form has an is_active box; a missing value would untick it.
    fields["is_active"] = True
    form = form_class(fields, instance=address)
    if not form.is_valid():
        return _form_errors(form)
    changes = _changes(form, before, prefix=f"{title} - ")
    with transaction.atomic():
        saved = form.save(commit=False)
        saved.user = user
        saved.save()
        _email_hr(user, changes)
    return None


def _square_jpeg(upload):
    """Centre-crops the photo: the web form only accepts square images."""
    image = ImageOps.exif_transpose(Image.open(upload)).convert("RGB")
    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    if side > AVATAR_SIDE:
        image = image.resize((AVATAR_SIDE, AVATAR_SIDE))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    return output.getvalue()


def update_avatar(user, upload):
    """Returns errors or None."""
    if upload is None:
        return {"avatar": ["Choose a photo."]}
    if upload.size > MAX_AVATAR_BYTES:
        return {"avatar": ["The photo must be under 8 MB."]}
    try:
        content = _square_jpeg(upload)
    except (UnidentifiedImageError, OSError, ValueError):
        return {"avatar": ["Invalid image file. Please choose a valid photo."]}

    details = user.personal_detail
    old = details.avatar.name if details.avatar else ""
    file = SimpleUploadedFile(f"{user.username.lower()}.jpg", content, content_type="image/jpeg")
    form = AvatarUpdateForm({}, {"avatar": file}, instance=details)
    if not form.is_valid():
        return _form_errors(form)
    with transaction.atomic():
        saved = form.save()
        _email_hr(user, {"Avatar": (old, saved.avatar.name)})
    return None


def change_password(user, data):
    """Returns errors or None. The app then asks the user to sign in again."""
    form = ChangeUserPasswordForm(
        user,
        {
            "old_password": data.get("old_password") or "",
            "new_password1": data.get("new_password1") or "",
            "new_password2": data.get("new_password2") or "",
        },
    )
    if not form.is_valid():
        return _form_errors(form)
    user.is_password_changed = True  # same flag the web sets
    form.save()
    return None
