from django.utils import timezone
from django.core.exceptions import ValidationError
from hrms_app.models import (
    LeaveApplication,
    AttendanceLog,
    UserTour,
    LeaveDayChoiceAdjustment,
)
from hrms_app.hrms.utils import get_non_working_days
from django.conf import settings
from hrms_app.hrms.utils import *


def apply_leave_policies(user, leave_type, startDate, endDate, bookedLeave):
    if leave_type.leave_type_short_code == "CL":
        apply_cl_policy(user, leave_type, startDate, bookedLeave)
    elif leave_type.leave_type_short_code == "SL":
        pass  # No specific check needed as it can be applied on the same date
    elif leave_type.leave_type_short_code == "EL":
        apply_el_policy(user, leave_type, bookedLeave)


def apply_cl_policy(user, leave_type, startDate, bookedLeave):
    cl_min_days_notice = leave_type.min_notice_days
    cl_max_days = leave_type.max_days_limit
    if (startDate.date() - timezone.now().date()).days < cl_min_days_notice:
        raise ValidationError(
            f"CL should be applied at least {int(cl_min_days_notice)} days in advance."
        )
    if bookedLeave > cl_max_days:
        raise ValidationError(
            f"CL can be applied for a maximum of {int(cl_max_days)} days."
        )

    # Check for consecutive CL applications
    last_leave = (
        LeaveApplication.objects.filter(
            appliedBy=user,
            leave_type__leave_type_short_code="CL",
            status__in=[settings.APPROVED, settings.PENDING_CANCELLATION],
        )
        .order_by("-endDate")
        .first()
    )

    if last_leave:
        last_date = timezone.make_naive(last_leave.endDate)
        days_between = (startDate - last_date.date()).days
        if days_between <= 1:
            raise ValidationError("Consecutive CL applications are not allowed.")
        non_working_days = get_non_working_days(last_date.date(), startDate)
        if days_between - non_working_days <= non_working_days:
            raise ValidationError("Consecutive CL applications are not allowed.")


def apply_el_policy(user, leave_type, bookedLeave):
    allowed_days_per_year = leave_type.allowed_days_per_year
    min_notice_days = leave_type.min_notice_days
    max_days_limit = leave_type.max_days_limit
    min_days_limit = leave_type.min_days_limit
    if bookedLeave > max_days_limit:
        raise ValidationError(
            f"EL can be applied for maximum ({max_days_limit}) days."
        )

    if bookedLeave < min_days_limit:
        raise ValidationError(
            f"EL can be applied for minimum ({min_days_limit}) days."
        )

    current_fy_start = leave_type.leave_fy_start
    current_fy_end = leave_type.leave_fy_end
    if not (current_fy_start and current_fy_end):
        raise ValidationError(
            "Financial year start and end dates are not set for this leave type."
        )

    el_application_count = LeaveApplication.objects.filter(
        leave_type__leave_type_short_code="EL",
        appliedBy=user,
        startDate__gte=current_fy_start,
        startDate__lte=current_fy_end,
        status__in=[settings.APPROVED, settings.PENDING_CANCELLATION],
    ).count()
    if el_application_count >= allowed_days_per_year:
        raise ValidationError(
            f"EL can be applied a maximum of {allowed_days_per_year} times in the financial year."
        )


def check_overlapping_leaves(user, startDate, endDate):
    if LeaveApplication.objects.filter(
        appliedBy=user,
        startDate__lte=endDate,
        endDate__gte=startDate,
        status__in=[settings.APPROVED, settings.PENDING_CANCELLATION],
    ).exists():
        raise ValidationError(
            "There is an overlapping leave application in the selected date range."
        )


def get_employee_requested_leave(user, status=None):
    leave_status = status if status is not None else settings.PENDING

    if user.is_superuser:
        # If the user is a superuser, fetch all leave applications with the given status
        employee_leaves = [
            {
                "leaveApplication": leaveApplication,
                "start_date": format_date(leaveApplication.startDate),
                "end_date": format_date(leaveApplication.endDate),
            }
            for leaveApplication in LeaveApplication.objects.filter(status=leave_status)
        ]
    else:
        # Fetch leave applications for employees assigned to the user
        employee_leaves = []
        employees = user.employees.all()
        for employee in employees:
            employee_leaves.extend(
                [
                    {
                        "leaveApplication": leaveApplication,
                        "start_date": format_date(leaveApplication.startDate),
                        "end_date": format_date(leaveApplication.endDate),
                    }
                    for leaveApplication in employee.leaves.filter(status=leave_status)
                ]
            )

    return employee_leaves

def get_employee_requested_tour(user, status=None):
    tour_status = status if status is not None else settings.PENDING

    if user.is_superuser:
        # Fetch all tours with the given status for superusers
        return UserTour.objects.filter(status=tour_status)
    else:
        # Fetch tours applied by employees assigned to the user
        return UserTour.objects.filter(applied_by__in=user.employees.all(), status=tour_status)


def get_regularization_requests(user, status=None):
    reg_status = status if status is not None else settings.PENDING

    if user.is_superuser:
        # Fetch all regularization requests with the given status for superusers
        return AttendanceLog.objects.filter(is_submitted=True, status=reg_status)
    else:
        # Fetch regularization requests applied by employees assigned to the user
        return AttendanceLog.objects.filter(
            applied_by__in=user.employees.all(), is_submitted=True, status=reg_status
        )

def format_date(date):
    from django.utils.timezone import make_aware, make_naive

    naive_date = make_naive(date)
    output_format = "%Y-%m-%d"
    formatted_date = naive_date.strftime(output_format)
    return formatted_date


class LeavePolicyManager:
    def __init__(
        self, user, leave_type, start_date, end_date, start_day_choice, end_day_choice
    ):
        self.user = user
        self.leave_type = leave_type
        self.start_date = start_date
        self.adjusted_start_date = start_date
        self.end_date = end_date
        self.start_day_choice = start_day_choice
        self.end_day_choice = end_day_choice

        # Calculate booked leave using the new function
        self.booked_leave = calculate_total_days(
            start_date, end_date, start_day_choice, end_day_choice
        )

    def validate_policies(self):
        """
        Validates all leave policies applicable to the leave application.
        """
        self.validate_overlapping_leaves()
        self.validate_consecutive_leave_restrictions()

        if self.leave_type.leave_type_short_code == "CL":
            self.apply_cl_policy()
        elif self.leave_type.leave_type_short_code == "EL":
            self.apply_el_policy()

    def validate_overlapping_leaves(self):
        """
        Checks for overlapping leave applications for the user.
        """
        if LeaveApplication.objects.filter(
            appliedBy=self.user,
            startDate__lte=self.end_date,
            endDate__gte=self.start_date,
            status__in=[
                settings.APPROVED,
                settings.PENDING,
                settings.PENDING_CANCELLATION,
            ],
        ).exists():
            raise ValidationError(
                "There is an overlapping leave application in the selected date range."
            )

    def validate_consecutive_leave_restrictions(self):
        """
        Enforce the consecutive leave restrictions based on the `LeaveType` settings.
        """
        last_leave = (
            LeaveApplication.objects.filter(
                appliedBy=self.user,
                status__in=[
                    settings.APPROVED,
                    settings.PENDING,
                    settings.PENDING_CANCELLATION,
                ],
            )
            .order_by("-endDate")
            .first()
        )

        if not last_leave:
            return  # No previous leaves to check against

        last_leave_type = last_leave.leave_type

        # Handle timezone-aware datetime for last_end_date
        last_end_date = (
            timezone.localtime(last_leave.endDate)
            if timezone.is_aware(last_leave.endDate)
            else last_leave.endDate
        )
        last_end_day_choice = last_leave.endDayChoice

        days_between =(1 - calculate_total_days(
                start_date=last_end_date.date(),
                end_date=self.start_date.date(),
                start_day_choice=last_end_day_choice,
                end_day_choice=self.start_day_choice))
        
        non_work_day = get_non_working_days(
                start=last_end_date.date(), end=self.start_date.date()
            )     
        if self.leave_type.leave_type_short_code == "CL" and last_leave.leave_type.leave_type_short_code == "CL":
            days_between -= non_work_day
            
        if (
            self.leave_type.consecutive_restriction
            and last_leave_type == self.leave_type
            and days_between <= last_leave.leave_type.min_days_limit
        ):
            raise ValidationError(
                f"Consecutive {self.leave_type} applications are not allowed."
            )

        if (
            last_leave_type in self.leave_type.restricted_after_leave_types.all()
            and days_between <= last_leave.leave_type.min_days_limit
        ):
            raise ValidationError(
                f"You cannot apply for {self.leave_type} immediately after {last_leave_type}. "
                f"Please choose a different leave type or wait a few days."
            )

    def apply_cl_policy(self):
        """
        Applies Casual Leave specific policies.
        """
        self.apply_min_notice_days_policy("CL")
        self.apply_max_days_limit_policy("CL")

    def apply_el_policy(self):
        """
        Applies Earned Leave specific policies.
        """
        el_allowed_days = self.leave_type.allowed_days_per_year
        el_min_days = self.leave_type.min_notice_days

        if self.booked_leave > el_allowed_days:
            raise ValidationError(
                f"EL can be applied for a maximum of {el_allowed_days} days in the financial year."
            )

        current_fy_start = self.leave_type.leave_fy_start
        current_fy_end = self.leave_type.leave_fy_end

        if not (current_fy_start and current_fy_end):
            raise ValidationError(
                "Financial year start and end dates are not set for this leave type."
            )

        el_application_count = LeaveApplication.objects.filter(
            leave_type__leave_type_short_code="EL",
            appliedBy=self.user,
            startDate__gte=current_fy_start,
            startDate__lte=current_fy_end,
            status__in=[settings.APPROVED, settings.PENDING_CANCELLATION],
        ).count()

        if el_application_count >= el_min_days:
            raise ValidationError(
                f"EL can be applied a maximum of {el_min_days} times in the financial year."
            )

    def apply_min_notice_days_policy(self, leave_type_short_code):
        """
        Applies minimum notice days policy for Casual Leave.
        """
        min_notice_days = self.leave_type.min_notice_days
        if (self.start_date.date() - timezone.now().date()).days < min_notice_days:
            raise ValidationError(
                f"{leave_type_short_code} should be applied at least {int(min_notice_days)} days in advance."
            )

    def apply_max_days_limit_policy(self, leave_type_short_code):
        """
        Applies maximum days limit policy for Casual Leave.
        """
        max_days = self.leave_type.max_days_limit
        if self.booked_leave > max_days:
            raise ValidationError(
                f"{leave_type_short_code} can be applied for a maximum of {int(max_days)} days."
            )


def calculate_total_days(start_date, end_date, start_day_choice, end_day_choice):
    """
    Calculate total leave days between the start and end dates, considering start and end day choices.
    Uses database-stored adjustment values for flexibility.
    Ensures the result is always positive.
    """
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    total_days = (end_date - start_date).days + 1
    try:
        adjustment = LeaveDayChoiceAdjustment.objects.get(
            start_day_choice=start_day_choice, end_day_choice=end_day_choice
        ).adjustment_value
    except LeaveDayChoiceAdjustment.DoesNotExist:
        adjustment = 0

    total_days -= adjustment
    if start_date == end_date:
        if start_day_choice in [
            settings.FIRST_HALF,
            settings.SECOND_HALF,
        ] and end_day_choice in [settings.FIRST_HALF, settings.SECOND_HALF]:
            return 0.5
        return 1.0

    return float(total_days)  # Return as float for consistency
