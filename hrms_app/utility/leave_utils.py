from django.utils import timezone
from django.core.exceptions import ValidationError
from hrms_app.models import (
    LeaveApplication,
    AttendanceLog,
    UserTour,
    LeaveDayChoiceAdjustment,
    LeaveBalanceOpenings,
)
from hrms_app.hrms.utils import get_non_working_days
from django.conf import settings
from hrms_app.hrms.utils import *


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
            for leaveApplication in LeaveApplication.objects.filter(
                status__in=[leave_status, settings.RECOMMEND]
            )
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
                    for leaveApplication in employee.leaves.filter(
                        status__in=[leave_status, settings.PENDING_CANCELLATION]
                    )
                ]
            )
        if user.personal_detail.designation.department.department == "admin":
            employee_leaves.extend(
                {
                    "leaveApplication": leaveApplication,
                    "start_date": format_date(leaveApplication.startDate),
                    "end_date": format_date(leaveApplication.endDate),
                }
                for leaveApplication in LeaveApplication.objects.filter(
                    status=settings.RECOMMEND
                )
            )
    return employee_leaves


def get_employee_requested_tour(user, status=None):
    tour_status = status if status is not None else settings.PENDING
    if user.is_superuser:
        # Fetch all tours with the given status for superusers
        return UserTour.objects.filter(status=tour_status)
    else:
        # Fetch tours applied by employees assigned to the user
        return UserTour.objects.filter(
            applied_by__in=user.employees.all(),
            status__in=[tour_status, settings.EXTENDED],
        )


def get_regularization_requests(user, status=None):
    reg_status = status if status is not None else settings.PENDING

    if user.is_superuser:
        # Fetch all regularization requests with the given status for superusers
        return AttendanceLog.objects.filter(
            is_submitted=True, regularized=False, status=reg_status
        )
    elif user.personal_detail.designation.department.department == "admin":
        return AttendanceLog.objects.filter(
            is_submitted=True,
            regularized=False,
            status__in=[reg_status],
            applied_by__in=user.employees.all(),
        ) | AttendanceLog.objects.filter(
            is_submitted=True, regularized=False, status=settings.RECOMMEND
        )

    else:
        # Fetch regularization requests applied by employees assigned to the user
        return AttendanceLog.objects.filter(
            applied_by__in=user.employees.all(),
            is_submitted=True,
            regularized=False,
            status=reg_status,
        )


def format_date(date):
    from django.utils.timezone import make_aware, make_naive

    naive_date = make_naive(date)
    output_format = "%Y-%m-%d"
    formatted_date = naive_date.strftime(output_format)
    return formatted_date


logger = logging.getLogger(__name__)


def filter_leaves(queryset, form):
    """Apply filters to a LeaveApplication queryset based on form data."""
    if form.is_valid():
        status = form.cleaned_data.get("status")
        from_date = form.cleaned_data.get("fromDate")
        to_date = form.cleaned_data.get("toDate")
        if status:
            queryset = queryset.filter(status=status)
        if from_date:
            queryset = queryset.filter(startDate__gte=from_date)
        if to_date:
            queryset = queryset.filter(endDate__lte=to_date)
    return queryset


def get_filtered_leaves(self, user, form):
    """Apply filters to the leave applications."""
    try:
        employee_leaves = LeaveApplication.objects.filter(
            appliedBy__in=user.employees.all()
        )
        return filter_leaves(employee_leaves, form)
    except ValidationError as ve:
        logger.warning(f"Validation error while filtering leaves: {ve}")
        return LeaveApplication.objects.none()
    except Exception as e:
        logger.exception(f"Unexpected error while filtering leaves: {e}")
        return LeaveApplication.objects.none()


class LeavePolicyManager:
    def __init__(
        self,
        user,
        leave_type,
        start_date,
        end_date,
        start_day_choice,
        end_day_choice,
        bookedLeave,
        exclude_application_id=None
    ):
        self.user = user
        self.leave_type = leave_type
        self.start_date = start_date
        self.adjusted_start_date = start_date
        self.end_date = end_date
        self.start_day_choice = start_day_choice
        self.end_day_choice = end_day_choice
        self.booked_leave = bookedLeave
        self.exclude_application_id = exclude_application_id

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
        elif self.leave_type.leave_type_short_code == "SL":
            self.apply_sl_policy()

    def validate_overlapping_leaves(self):
        """
        Checks for overlapping leave applications for the user.
        """
        overlapping_leaves = LeaveApplication.objects.filter(
            appliedBy=self.user,
            startDate__lte=self.start_date, 
            endDate__gte=self.start_date,
            status__in=[
                settings.APPROVED,
                settings.PENDING,
                settings.PENDING_CANCELLATION,
            ],
        ).exclude(id=self.exclude_application_id)
        if overlapping_leaves.exists():
            raise ValidationError(
                "There is an overlapping leave application in the selected date range."
            )

    def apply_cl_policy(self):
        """
        Applies Casual Leave specific policies.
        """
        self.apply_min_notice_days_policy()  # this function checks the minimum notice day for that particular leave type
        self.validate_min_days()  # this function checks the minimum days allowed for that particular leave type
        self.apply_max_days_limit_policy()  # this function checks the maximum notice day for that particular leave type
        self.apply_sl_policy()
        
        
    def apply_sl_policy(self):
        current_date = timezone.now().date()
        non_working_days = get_non_working_days(start=self.end_date.date(),end=current_date)
        gap = (current_date - self.end_date.date()).days + 1
        gap = gap - non_working_days
        if gap > 3:
            raise ValidationError(f"{self.leave_type.leave_type_short_code} application denied.You can apply within 3 working days.")

    def validate_min_days(self):
        if float(self.booked_leave) < float(self.leave_type.min_days_limit):
            raise ValidationError(
                "Total day(s) leave is less than the minimum allowed days limit."
            )

    def apply_el_policy(self):
        """
        Applies Earned Leave specific policies.
        """
        el_allowed_days = self.leave_type.allowed_days_per_year
        self.apply_min_notice_days_policy()
        if (
            not isinstance(self.booked_leave, (int, float))
            or self.booked_leave % 1 != 0
        ):
            raise ValidationError(
                f"EL can only be applied for whole days. Half days like {self.booked_leave} are not allowed."
            )
        self.validate_min_days()  # this function checks the minimum days allowed for that particular leave type
        self.apply_max_days_limit_policy()  # this function checks the maximum notice day for that particular leave type
        el_application_count = LeaveApplication.objects.filter(
            leave_type__leave_type_short_code="EL",
            appliedBy=self.user,
            startDate__gte=self.leave_type.leave_fy_start,
            startDate__lte=self.leave_type.leave_fy_end,
            status__in=[
                settings.PENDING,
                settings.APPROVED,
                settings.PENDING_CANCELLATION,
            ],
        ).exclude(id=self.exclude_application_id).count()

        if el_application_count >= el_allowed_days:
            raise ValidationError(
                f"EL can be applied a maximum of {el_allowed_days} times in the financial year."
            )

    def apply_min_notice_days_policy(self):
        """
        Applies minimum notice days policy for Casual Leave.
        """
        min_notice_days = self.leave_type.min_notice_days
        if min_notice_days is None:
            return
        if (self.start_date.date() - timezone.now().date()).days < int(min_notice_days):
            raise ValidationError(
                f"{self.leave_type.leave_type_short_code} should be applied at least {min_notice_days} days in advance."
            )

    def apply_max_days_limit_policy(self):
        """
        Applies maximum days limit policy for Casual Leave.
        """
        max_days = self.leave_type.max_days_limit
        if max_days is None:
            return
        if float(self.booked_leave) > int(max_days):
            raise ValidationError(
                f"{self.leave_type.leave_type_short_code} can be applied for a maximum of {max_days} days."
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
                endDate__lt=self.start_date,
            ).exclude(id=self.exclude_application_id)
            .order_by("-endDate")
            .first()
        )

        if not last_leave:
            return
        last_leave_type = last_leave.leave_type
        last_end_date = (
            timezone.localtime(last_leave.endDate).date()
            if timezone.is_aware(last_leave.endDate)
            else last_leave.endDate.date()
        )
        last_end_day_choice = last_leave.endDayChoice
        days_between = calculate_day_difference_btn_last_current_leave(
            last_leave_date=last_end_date,
            current_leave_date=self.start_date.date(),
            last_end_day_choice=last_end_day_choice,
            current_start_day_choice=self.start_day_choice,
        )
        non_work_days = get_non_working_days(
            start=last_end_date, end=self.start_date.date()
        )
        if (
            self.leave_type.leave_type_short_code == "CL"
            and last_leave.leave_type.leave_type_short_code == "CL"
        ):
            days_between -= non_work_days
        if (
            self.leave_type in last_leave_type.restricted_after_leave_types.all()
            and days_between <= 0
        ):
            raise ValidationError(
                f"You cannot apply for {self.leave_type} immediately after {last_leave_type}. "
                f"Please choose a different leave type or wait a few days."
            )


def calculate_day_difference_btn_last_current_leave(
    last_leave_date, current_leave_date, last_end_day_choice, current_start_day_choice
):
    """
    Calculate total leave days between the start and end dates, considering start and end day choices.
    Uses database-stored adjustment values for flexibility.
    Ensures the result is always positive and handles timezone-aware dates.
    """
    if last_leave_date > current_leave_date:
        last_leave_date, current_leave_date = current_leave_date, last_leave_date
    total_days = (current_leave_date - last_leave_date).days
    if last_end_day_choice == settings.FIRST_HALF or current_start_day_choice == settings.SECOND_HALF:
        total_days -= 0.5
    elif current_start_day_choice == settings.FULL_DAY or last_end_day_choice == settings.FULL_DAY :
        total_days -= 1
    final_days = max(float(total_days), 0.0)
    return final_days


def calculate_total_leave_days(start_date, end_date, start_day_choice, end_day_choice):
    """
    Calculate total leave days between the start and end dates, considering start and end day choices.
    Uses database-stored adjustment values for flexibility.
    Ensures the result is always positive.
    """
    if start_date == end_date:
        if start_day_choice in [
            settings.FIRST_HALF,
            settings.SECOND_HALF,
        ] and end_day_choice in [settings.FIRST_HALF, settings.SECOND_HALF]:
            return 0.5
        return 1.0
    else:
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        total_days = (end_date - start_date).days
        try:
            adjustment = LeaveDayChoiceAdjustment.objects.get(
                start_day_choice=start_day_choice, end_day_choice=end_day_choice
            ).adjustment_value
        except LeaveDayChoiceAdjustment.DoesNotExist:
            adjustment = 0
        total_days -= adjustment
        return float(total_days)


def get_current_financial_year():
    today = datetime.today()
    current_year = today.year
    if today.month < 4:
        fy_start = datetime(current_year - 1, 4, 1)
        fy_end = datetime(current_year, 3, 31)
    else:  # April or later
        fy_start = datetime(current_year, 4, 1)
        fy_end = datetime(current_year + 1, 3, 31)
    return fy_start, fy_end


from django.db.models import Sum
from django.db.models.functions import TruncMonth


class LeaveStatsManager:
    def __init__(self, user, leave_type):
        self.user = user
        self.leave_type = leave_type

    def get_on_hold_leave(self):
        return (
            LeaveApplication.objects.filter(
                appliedBy=self.user, status="PENDING", leave_type=self.leave_type
            ).aggregate(total=Sum("usedLeave"))["total"]
            or 0
        )

    def get_approved_leave_total(self):
        return (
            LeaveApplication.objects.filter(
                appliedBy=self.user, status="pending", leave_type=self.leave_type
            ).aggregate(total=Sum("usedLeave"))["total"]
            or 0
        )

    def get_el_applied_times(self):
        el_application_count = LeaveApplication.objects.filter(
            leave_type__leave_type_short_code=self.leave_type.leave_type_short_code,
            appliedBy=self.user,
            startDate__gte=self.leave_type.leave_fy_start,
            startDate__lte=self.leave_type.leave_fy_end,
            status__in=[
                settings.PENDING,
                settings.APPROVED,
                settings.PENDING_CANCELLATION,
            ],
        ).count()
        return el_application_count

    def get_opening_balance(self, year):
        record = LeaveBalanceOpenings.objects.filter(
            user=self.user, leave_type=self.leave_type, year=year
        ).first()
        return record.remaining_leave_balances if record else 0

    def get_remaining_balance(self, year):
        return self.get_opening_balance(year=year) - self.get_approved_leave_total()

    def get_monthly_report(self, year):
        qs = (
            LeaveApplication.objects.filter(
                appliedBy=self.user,
                status="APPROVED",
                leave_type=self.leave_type,
                startDate__year=year,
            )
            .annotate(month=TruncMonth("startDate"))
            .values("month")
            .annotate(total=Sum("usedLeave"))
            .order_by("month")
        )

        report = defaultdict(lambda: 0)
        for item in qs:
            report[item["month"].strftime("%B")] = item["total"]
        return dict(report)
