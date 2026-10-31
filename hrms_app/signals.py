# myapp/signals.py
import logging

from django.db import transaction
from .tasks import (
    send_admin_leave_notification,
    send_leave_application_notifications,
    send_tour_notifications,
)
from django.contrib.sites.models import Site
from django.utils.text import slugify
from .models import LeaveApplication, UserTour, Notification,LeaveBalanceOpenings,CustomUser,AttendanceLog
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save,pre_delete,pre_save
from django.dispatch import receiver
from django.conf import settings
from hrms_app.models import *
from django.core.exceptions import ImproperlyConfigured
from hrms_app.hrms.utils import check_lock_status
from hrms_app.services.leave_approval import admin_department_users
from hrms_app.services.workflow_messages import (
    admin_recommendation_text,
    build_messages,
    leave_label,
    tour_label,
)

# @receiver(post_save, sender=CustomUser)
# def initialize_leave_balance(sender, instance, created, **kwargs):
#     if created:
#         current_year = timezone.now().year
#         leave_types =LeaveType.objects.all()
#         LeaveBalanceOpenings.initialize_leave_balances(instance,leave_types, current_year, created_by=instance)



@receiver(pre_save, sender=None)
def set_user_fields(sender, instance, **kwargs):
    """
    Generic signal to set created_by and updated_by fields for multiple models.
    """
    request = getattr(settings, 'CURRENT_REQUEST', None)

    if request and hasattr(request, 'user'):
        user = request.user
    elif hasattr(instance, '_current_user'):
        user = instance._current_user
    else:
        user = None

    if user:
        # For new instance
        if instance.pk is None:
            if hasattr(instance, 'created_by'):
                instance.created_by = user
        # For updating instance
        if hasattr(instance, 'updated_by'):
            instance.updated_by = user


def _acting_user(fallback):
    """User of the current request (e.g. the approving manager), else ``fallback``."""
    request = getattr(settings, 'CURRENT_REQUEST', None)
    user = getattr(request, 'user', None)
    return user if user is not None and user.is_authenticated else fallback


def _notify_workflow_change(instance, created, applicant, *, label, notification_type, target_url, go_route):
    """Tells the employee and their manager, each in their own words, when a
    leave/tour is created or changes status. Saves that don't change the
    status notify nobody. Returns (employee text, manager text), or None.
    """
    status = instance.status
    old_status = getattr(instance, '_old_status', None)
    if not created and old_status == status:
        return None

    # _actor: set by services that know who decided (a JWT API request has no
    # user at middleware level).
    actor = getattr(instance, '_actor', None) or _acting_user(None)
    texts = build_messages(
        status,
        label,
        applicant,
        actor=actor,
        rerequested=getattr(instance, '_rerequested', False),
    )
    manager = applicant.reports_to
    for receiver, message in ((applicant, texts[0]), (manager, texts[1])):
        if receiver is None:
            continue
        Notification.objects.create(
            sender=actor or applicant,
            receiver=receiver,
            message=message,
            notification_type=notification_type,
            related_object_id=instance.id,
            related_content_type=ContentType.objects.get_for_model(type(instance)),
            target_url=target_url,
            go_route_mobile=go_route,
        )
    return texts


def _queue_emails(task, instance_id, texts):
    """Queues the two emails after commit, so a rolled-back action sends none."""
    domain = Site.objects.get_current().domain

    def enqueue():
        try:
            task.delay(instance_id, 'https', domain, employee_text=texts[0], manager_text=texts[1])
        except Exception:
            logging.getLogger(__name__).exception("Could not queue the emails for %s", instance_id)

    transaction.on_commit(enqueue)


def _notify_admin_department(leave):
    """A recommended LWP waits for the admin department: tell them too."""
    applicant = leave.appliedBy
    actor = getattr(leave, '_actor', None) or _acting_user(None)
    message = admin_recommendation_text(leave_label(leave), applicant, actor)
    admins = admin_department_users().exclude(pk__in=[applicant.pk, applicant.reports_to_id or 0])
    receiver_ids = []
    for admin in admins:
        receiver_ids.append(admin.pk)
        Notification.objects.create(
            sender=actor or applicant,
            receiver=admin,
            message=message,
            notification_type=settings.LEAVE_STATUS,
            related_object_id=leave.id,
            related_content_type=ContentType.objects.get_for_model(LeaveApplication),
            target_url=f"/leave/{leave.slug}/",
            go_route_mobile='leave-detail',
        )
    if not receiver_ids:
        return

    domain = Site.objects.get_current().domain

    def enqueue():
        try:
            send_admin_leave_notification.delay(leave.id, 'https', domain, message, receiver_ids)
        except Exception:
            logging.getLogger(__name__).exception("Could not queue the admin email for %s", leave.id)

    transaction.on_commit(enqueue)


@receiver(pre_save, sender=LeaveApplication)
@receiver(pre_save, sender=UserTour)
def remember_old_status(sender, instance, **kwargs):
    """Lets post_save tell a status change from any other edit."""
    instance._old_status = (
        sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
        if instance.pk
        else None
    )


@receiver(post_save, sender=LeaveApplication)
def create_or_update_leave_log(sender, instance, created, **kwargs):
        if created:
            # Create Leave Log
            LeaveLog.create_log(instance, instance.appliedBy, 'Created')
        texts = _notify_workflow_change(
            instance,
            created,
            instance.appliedBy,
            label=leave_label(instance),
            notification_type=settings.LEAVE_STATUS,
            target_url=f"/leave/{instance.slug}/",
            go_route='leave-detail',
        )
        if texts:
            _queue_emails(send_leave_application_notifications, instance.id, texts)
        if texts and instance.status == settings.RECOMMEND:
            _notify_admin_department(instance)

@receiver(post_save, sender=UserTour)
def create_or_update_user_tour(sender, instance, created, **kwargs):
        if created:
            # Create Tour Status Log
            TourStatusLog.create_log(tour=instance, action_by=instance.applied_by, action='Created')
    
        texts = _notify_workflow_change(
            instance,
            created,
            instance.applied_by,
            label=tour_label(instance),
            notification_type=settings.TOUR_STATUS,
            target_url=f"/tour/{instance.slug}/",
            go_route='tour-detail',
        )
        # The apply views email a new tour themselves.
        if texts and not created:
            _queue_emails(send_tour_notifications, instance.id, texts)


@receiver(pre_save, sender=UserTour)
def set_user_tour_slug(sender, instance, **kwargs):
    if not instance.slug:
        slug_base = slugify(f"{instance.applied_by.get_full_name()}-{instance.from_destination}-{instance.to_destination}")
        slug = slug_base
        num = 1
        while UserTour.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{num}"
            num += 1
        instance.slug = slug

from django.conf import settings
from django.utils.timezone import localtime
from datetime import timedelta

@receiver(post_save, sender=LeaveApplication)
def create_or_update_leave_days(sender, instance, created, **kwargs):

    if not instance.startDate or not instance.endDate:
        return

    # Clear existing days before recreating
    instance.leave_days.all().delete()

    current_date = localtime(instance.startDate).date()
    end_date = localtime(instance.endDate).date()

    start_date = current_date
    end_date_exact = end_date

    # 🔹 Get leave type short code safely
    leave_code = None
    if instance.leave_type:
        leave_code = instance.leave_type.leave_type_short_code

    while current_date <= end_date:

        # 🔹 Skip Sunday ONLY if leave type is NOT EL
        if current_date.weekday() == 6 and leave_code != "EL":
            current_date += timedelta(days=1)
            continue

        if current_date == start_date:
            is_full_day = (instance.startDayChoice == settings.FULL_DAY)
        elif current_date == end_date_exact:
            is_full_day = (instance.endDayChoice == settings.FULL_DAY)
        else:
            is_full_day = True

        LeaveDay.objects.create(
            leave_application=instance,
            date=current_date,
            is_full_day=is_full_day,
        )

        current_date += timedelta(days=1)
        
@receiver(post_save, sender=CustomUser)
def create_employee_shift(sender, instance, created, **kwargs):
    """
    Create an EmployeeShift instance after a CustomUser is created.
    """
    if created:  # Only create shifts for newly created users
        try:
            default_shift_timing = ShiftTiming.objects.first()  # Replace with your logic for default shift
            if default_shift_timing:
                EmployeeShift.objects.create(
                    employee=instance,
                    shift_timing=default_shift_timing,
                    created_by=instance,  # Assuming the user is self-created; adjust logic as needed
                )
        except Exception as e:
            # Log the error or handle it if no default ShiftTiming exists
            print(f"Error creating EmployeeShift: {e}")

# signals.py

@receiver(pre_save, sender=LeaveApplication)
@receiver(pre_save, sender=AttendanceLog)
@receiver(pre_save, sender=UserTour)
def prevent_save_if_locked(sender, instance, **kwargs):
    """
    Prevent saving an instance if the action is locked for the relevant period.
    Dynamically fetches the correct date field for the instance.
    """
    instance_date = get_instance_date(instance, sender)
    check_lock_status(instance_date=instance_date)

@receiver(pre_delete, sender=LeaveApplication)
@receiver(pre_delete, sender=AttendanceLog)
@receiver(pre_delete, sender=UserTour)
def prevent_delete_if_locked(sender, instance, **kwargs):
    """
    Prevent deleting an instance if the action is locked for the relevant period.
    Dynamically fetches the correct date field for the instance.
    """
    instance_date = get_instance_date(instance, sender)
    check_lock_status(instance_date=instance_date)


def get_instance_date(instance, sender):
    """
    Dynamically retrieves the correct date field from the instance based on the model type.
    Raises ImproperlyConfigured if the date field is not found.
    """
    if sender in (AttendanceLog, UserTour) and hasattr(instance, 'start_date'):
        return instance.start_date
    elif sender == LeaveApplication and hasattr(instance, 'startDate'):
        return instance.startDate
    else:
        raise ImproperlyConfigured(
            f"The model {sender.__name__} does not have a recognized date field for lock validation."
        )


from .models import HRAnnouncement
from .tasks import send_announcement_email_task

@receiver(post_save, sender=HRAnnouncement)
def send_announcement_signal(sender, instance, created, **kwargs):
    send_announcement_email_task.delay(instance.id, created)



@receiver(post_save, sender=Notification)
def push_new_notification_to_mobile(sender, instance, created, **kwargs):
    """Mirror every new in-app notification to the receiver's phone (FCM)."""
    if not created or instance.receiver_id is None:
        return

    def enqueue():
        from .tasks import send_notification_push

        try:
            send_notification_push.delay(instance.pk)
        except Exception:
            # Broker unavailable: send inline rather than drop the push.
            from .services.notification_push import push_notification_to_device

            try:
                push_notification_to_device(instance)
            except Exception:
                logging.getLogger(__name__).exception("FCM push failed for %s", instance.pk)

    transaction.on_commit(enqueue)
