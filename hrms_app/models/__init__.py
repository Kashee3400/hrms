"""
Models package for hrms_app.

Split from a single models.py into one file per domain. Every model is
re-exported here so existing code doing `from hrms_app.models import X` or
`from .models import X` keeps working unchanged.
"""
from django.utils import timezone


def _current_year():
    """
    Kept in this __init__ module (not moved into leave.py) so its dotted
    path stays `hrms_app.models._current_year`, matching what's already
    recorded as a field default in migration 0041.
    """
    return timezone.now().year


from .core import Role, CustomUser, Logo
from .organization import Department, Designation, OfficeLocation
from .employee import (
    Gender,
    MaritalStatus,
    PermanentAddress,
    CorrespondingAddress,
    Religion,
    Family,
    PersonalDetails,
    BankDetails,
)
from .shift import ShiftTiming, EmployeeShift
from .leave import (
    LeaveLog,
    LeaveApplication,
    LeaveDay,
    LeaveDayChoiceAdjustment,
    LeaveType,
    LeaveStatusPermission,
    LeaveBalanceOpenings,
    LeaveTransaction,
)
from .compensatory_off import CompensatoryOff, CompensatoryOffLog
from .attendance import (
    DeviceInformation,
    AttendanceLog,
    AttendanceLogHistory,
    AttendanceLogAction,
    AttendanceSetting,
    AttendanceStatusColor,
    OffDay,
    LockStatus,
    AttendanceCache,
    AttendanceCacheLog,
)
from .tour import (
    make_datetime_aware,
    UserTour,
    TourStatusLog,
    TourDateTimeChangeLog,
    Bill,
)
from .holiday import Holiday, WishingCard, HRAnnouncement, OfficeClosure
from .notification import Notification, NotificationSetting
from .misc import AppSetting, FormProgress, SentEmail, EmailOTP

__all__ = [
    "Role",
    "CustomUser",
    "Logo",
    "Department",
    "Designation",
    "OfficeLocation",
    "Gender",
    "MaritalStatus",
    "PermanentAddress",
    "CorrespondingAddress",
    "Religion",
    "Family",
    "PersonalDetails",
    "BankDetails",
    "ShiftTiming",
    "EmployeeShift",
    "LeaveLog",
    "LeaveApplication",
    "LeaveDay",
    "LeaveDayChoiceAdjustment",
    "LeaveType",
    "LeaveStatusPermission",
    "LeaveBalanceOpenings",
    "LeaveTransaction",
    "CompensatoryOff",
    "CompensatoryOffLog",
    "DeviceInformation",
    "AttendanceLog",
    "AttendanceLogHistory",
    "AttendanceLogAction",
    "AttendanceSetting",
    "AttendanceStatusColor",
    "OffDay",
    "LockStatus",
    "AttendanceCache",
    "AttendanceCacheLog",
    "make_datetime_aware",
    "UserTour",
    "TourStatusLog",
    "TourDateTimeChangeLog",
    "Bill",
    "Holiday",
    "WishingCard",
    "HRAnnouncement",
    "OfficeClosure",
    "Notification",
    "NotificationSetting",
    "AppSetting",
    "FormProgress",
    "SentEmail",
    "EmailOTP",
]
