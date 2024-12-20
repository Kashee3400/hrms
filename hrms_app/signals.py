# myapp/signals.py
from .tasks import send_leave_application_notifications,send_tour_notifications
from django.contrib.sites.models import Site
from .models import LeaveApplication, UserTour, Notification,LeaveBalanceOpenings,CustomUser
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save,pre_delete,pre_init,pre_migrate,post_delete,post_init,post_migrate,pre_save
from django.dispatch import receiver
from django.conf import settings
from hrms_app.models import *


@receiver(post_save, sender=CustomUser)
def initialize_leave_balance(sender, instance, created, **kwargs):
    if created:
        current_year = timezone.now().year
        leave_types =LeaveType.objects.all()
        LeaveBalanceOpenings.initialize_leave_balances(instance,leave_types, current_year, created_by=instance)
        # shift_timing = ShiftTiming.objects.filter(role=instance.role).first()
        # EmployeeShift.objects.create(employee=instance,shift_timing=shift_timing)



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


@receiver(post_save, sender=LeaveBalanceOpenings)
def create_leave_transaction(sender, instance, created, **kwargs):
    if created:
        # Handle newly created leave balance
        pass
    else:
        # Handle updated leave balance
        if instance.closing_balance != instance.opening_balance:
            # Create a new LeaveTransaction instance
            LeaveTransaction.objects.create(
                user=instance.user,
                leave_balance=instance,
                leave_type=instance.leave_type,
                transaction_date=timezone.now(),
                days_applied=instance.closing_balance - instance.opening_balance,
                days_approved=instance.closing_balance - instance.opening_balance,
            )

@receiver(post_save, sender=LeaveApplication)
def create_or_update_leave_log(sender, instance, created, **kwargs):
        if created:
            # Create Leave Log
            LeaveLog.create_log(instance, instance.appliedBy, 'Created')
        
        # Prepare notification
        Notification.objects.create(
            sender=instance.appliedBy,
            receiver=instance.appliedBy.reports_to,  # assuming the user who applied is the receiver
            message=f"Leave application '{instance.applicationNo}' has been created.",
            notification_type=settings.LEAVE_STATUS,  # use the constant defined in your Notification model
            related_object_id=instance.id,
            related_content_type=ContentType.objects.get_for_model(LeaveApplication),
            target_url=f"/leave/{instance.slug}/",  # Use the slug for URL
            go_route_mobile = 'leave-detail'
        )

        # Send additional notifications if needed
        current_site = Site.objects.get_current()
        protocol = 'http'  # or 'https' if applicable
        domain = current_site.domain
        send_leave_application_notifications.delay(instance.id, protocol, domain)

@receiver(post_save, sender=UserTour)
def create_or_update_user_tour(sender, instance, created, **kwargs):
        if created:
            # Create Tour Status Log
            TourStatusLog.create_log(tour=instance, action_by=instance.applied_by, action='Created')
    
        # Prepare notification
        Notification.objects.create(
            sender=instance.applied_by,
            receiver=instance.applied_by.reports_to,
            message=f"Tour '{instance.slug}' has been created.",
            notification_type=settings.TOUR_STATUS,
            related_object_id=instance.id,
            related_content_type=ContentType.objects.get_for_model(UserTour),
            target_url=f"/tour/{instance.slug}/",
            go_route_mobile = 'tour-detail'
        )

        # Send additional notifications if needed
        current_site = Site.objects.get_current()
        protocol = 'http'  # or 'https' if applicable
        domain = current_site.domain
        send_tour_notifications.delay(instance.id, protocol, domain)

@receiver(pre_save, sender=UserTour)
def set_user_tour_slug(sender, instance, **kwargs):
    if not instance.slug:
        slug_base = slugify(f"{instance.applied_by.get_full_name()}-{instance.from_destination}-{instance.to_destination}")
        slug = slug_base
        num = 1

        # Ensure unique slug
        while UserTour.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{num}"
            num += 1

        instance.slug = slug


@receiver(post_save, sender=AttendanceLog)
def create_or_update_regularization(sender, instance, created, **kwargs):
    if created:
        return
    current_site = Site.objects.get_current()
    protocol = 'http'  # or 'http' if applicable
    domain = current_site.domain
    send_tour_notifications.delay(instance.id, protocol, domain)
    

@receiver(post_save, sender=LeaveApplication)
def create_leave_days(sender, instance, created, **kwargs):
    """
    Create LeaveDay instances after LeaveApplication is saved.
    """
    if created and instance.startDate and instance.endDate:
        current_date = instance.startDate.date()
        end_date = instance.endDate.date()
        
        while current_date <= end_date:
            if current_date == instance.startDate.date():
                is_full_day = (instance.startDayChoice == settings.FULL_DAY)
            elif current_date == instance.endDate.date():
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
