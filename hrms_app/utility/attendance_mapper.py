from collections import defaultdict
from datetime import timedelta
from django.utils.timezone import localtime
from django.db.models import Count, Q
from django.conf import settings
from hrms_app.models import (
    Holiday,
    AttendanceLog,
    LeaveDay,
    UserTour
)
from .report_utils import calculate_daily_tour_durations



class AttendanceMapper:
    """
    Optimized attendance data mapper with improved performance and maintainability.
    Handles FL (Festival/Holiday) display issue and consolidates redundant logic.
    
    OPTIMIZATIONS APPLIED:
    - Batch database queries with prefetch_related/select_related
    - Cache employee IDs and date lookups
    - Reduce N+1 query patterns
    - Pre-compute date ranges and filters
    """
    
    # Status hierarchy - higher priority statuses override lower ones
    STATUS_HIERARCHY = {
        "P": 10,      # Present
        "L": 9,       # Leave types (CL, SL, ML, EL)
        "CL": 9,      # Casual Leave
        "CLH": 9,     # Casual Leave Half
        "SL": 9,      # Sick Leave
        "SLH": 9,     # Sick Leave Half
        "PATH": 9,    # Sick Leave Half
        "PAT": 9,     # Sick Leave Half
        "ML": 9,      # Medical Leave
        "EL": 9,      # Emergency Leave
        "CO": 9,      # Compensatory Off
        "STL": 9,     # Short leave
        "LWP": 9,     # Leave Without Pay
        "T": 8,       # Tour
        "TH": 8,      # Tour
        "H": 7,       # Half day
        "FL": 6,      # Festival/Holiday
        "A": 5,       # Absent
        "AWOL": 3,    # Absent Without Leave
        "OFF": 2,     # Sunday/Weekend
    }
    
    WORKING_STATUSES = {"P", "L", "CL", "CLH", "CO", "SL", "SLH", "STL", "ML", "EL", "LWP", "PAT", "PATH", "FL", "H", "T"}
    ABSENT_STATUSES = {"A", "LWP", "AWOL"}

    def __init__(self, start_date_object, end_date_object):
        self.start_date = start_date_object
        self.end_date = end_date_object
        self.total_days = (end_date_object - start_date_object).days + 1
        self.sundays = self._get_sundays()
        self.attendance_data = defaultdict(lambda: defaultdict(list))
        
        # OPTIMIZATION: Cache for office closures (loaded once)
        self._office_closure_cache = None
        # OPTIMIZATION: Cache for STL lookups (batch loaded)
        self._stl_cache = None
    
    def _get_sundays(self):
        """Pre-compute all Sundays in the date range"""
        return {
            self.start_date + timedelta(days=i)
            for i in range(self.total_days)
            if (self.start_date + timedelta(days=i)).weekday() == 6
        }
    
    def _get_status_for_date(self, employee_data, date):
        """Get primary status for a date"""
        if date not in employee_data or not employee_data[date]:
            return "A"
        return employee_data[date][0].get("status", "A") or "A"
    
    def _should_override_status(self, existing_status, new_status):
        """Check if new status should override existing based on hierarchy"""
        existing_priority = self.STATUS_HIERARCHY.get(existing_status, 0)
        new_priority = self.STATUS_HIERARCHY.get(new_status, 0)
        return new_priority > existing_priority
    
    def map_attendance_data(self, attendance_logs, leave_logs, holidays, tour_logs):
        """Main method to aggregate all attendance data"""
        
        # OPTIMIZATION: Pre-load office closures once (avoid repeated queries)
        self._office_closure_cache = self._get_office_closures()
        
        # OPTIMIZATION: Batch load all STL data for the date range
        self._stl_cache = self._get_stl_cache(attendance_logs)
        
        # Process in order of priority to avoid unnecessary overrides
        self._process_attendance_logs(attendance_logs)
        self._process_tour_logs(tour_logs)
        self._process_holidays(holidays)
        self._process_leave_logs(leave_logs)
        self._add_sundays()
        self._apply_saturday_lwp_rule()
        self._apply_smart_sunday_logic()
        
        # OPTIMIZATION: Clear caches after processing
        self._office_closure_cache = None
        self._stl_cache = None
        
        return dict(self.attendance_data)
    
    def _get_stl_cache(self, attendance_logs):
        """
        OPTIMIZATION: Batch load all STL (Short Leave) records for the date range.
        This eliminates N+1 queries in _process_attendance_logs.
        Returns: dict[(employee_id, date)] -> bool
        """
        from ..models import LeaveDay
        
        # OPTIMIZATION: Extract unique employee IDs from attendance logs (avoid set operations in loop)
        employee_ids = {log.applied_by.id for log in attendance_logs}
        
        if not employee_ids:
            return {}
        
        # OPTIMIZATION: Single batch query instead of per-log queries
        stl_records = LeaveDay.objects.approved().filter(
            leave_application__appliedBy_id__in=employee_ids,
            date__range=[self.start_date, self.end_date],
            leave_application__leave_type__leave_type_short_code="STL",
        ).values_list('leave_application__appliedBy_id', 'date')
        
        # OPTIMIZATION: Build lookup dict for O(1) access
        return {(emp_id, date): True for emp_id, date in stl_records}
    
    def _process_attendance_logs(self, attendance_logs):
        """
        Process attendance logs with office closures and STL.
        OPTIMIZATION: Uses cached office closures and STL lookups.
        """
        for log in attendance_logs:
            employee_id = log.applied_by.id
            log_date = localtime(log.start_date).date()

            # 1️⃣ Check office closure (highest priority) - OPTIMIZATION: uses cache
            if log_date in self._office_closure_cache:
                status = "P"
                color = "#000000"
            else:
                # 2️⃣ Check STL for that employee on that date - OPTIMIZATION: O(1) lookup
                if self._stl_cache.get((employee_id, log_date), False):
                    status = "P"
                    color =  "#06B900"
                else:
                    # 3️⃣ Default attendance status
                    status = log.att_status_short_code
                    color = log.color_hex or "#000000"

            self._set_status(employee_id, log_date, status, color)
    
    def _process_tour_logs(self, tour_logs):
        """Process tour logs"""
        for log in tour_logs:
            employee_id = log.applied_by.id
            daily_durations = calculate_daily_tour_durations(
                log.start_date, log.start_time, log.end_date, log.end_time
            )
            
            for date, short_code, _ in daily_durations:
                self._set_status(employee_id, date, short_code, "#06c1c4")
    
    def _process_holidays(self, holidays):
        """
        Process holidays efficiently.
        OPTIMIZATION: Batch fetch applicable_users to avoid N+1 queries.
        """
        for holiday in holidays:
            start = holiday.start_date
            end = holiday.end_date or holiday.start_date
            days = (end - start).days + 1
            
            # OPTIMIZATION: Use values_list for lighter query (only IDs needed)
            applicable_users = set(
                holiday.applicable_users.values_list("id", flat=True)
            )
            
            # If no users specified, get all employees we've seen
            if not applicable_users:
                applicable_users = set(self.attendance_data.keys())
            
            # OPTIMIZATION: Pre-compute date range to avoid repeated timedelta in inner loop
            holiday_dates = [start + timedelta(days=i) for i in range(days)]
            
            # Apply holiday to all applicable dates and employees
            for date in holiday_dates:
                for emp_id in applicable_users:
                    self._set_status(
                        emp_id, date, holiday.short_code, holiday.color_hex
                    )

    def _process_leave_logs(self, leave_logs):
        """
        Process leave logs with improved logic.
        OPTIMIZATION: Access leave_application fields directly (assumed prefetched).
        """
        for log in leave_logs:
            employee_id = log.leave_application.appliedBy.id
            log_date = log.date
            leave_type = log.leave_application.leave_type
            leave_status = leave_type.leave_type_short_code
            half_status = leave_type.half_day_short_code
            color = leave_type.color_hex or "#a2a2a2"
            
            # Determine leave duration status
            status = leave_status if log.is_full_day else half_status
            
            # CL/SL (Casual/Sick Leave) has special handling
            if leave_status in ["CL", "SL"]:
                existing_status = self._get_status_for_date(
                    self.attendance_data[employee_id], log_date
                )
                
                # FL takes priority over CL
                if existing_status == "FL":
                    continue  # Skip, keep FL
                
                # OFF takes priority over CL on Sundays
                if existing_status == "OFF" and log_date.weekday() == 6:
                    continue  # Skip, keep OFF
            
            self._set_status(employee_id, log_date, status, color)
    
    def _set_status(self, employee_id, date, status, color):
        """Set status for an employee on a date using hierarchy"""
        existing_status = self._get_status_for_date(
            self.attendance_data[employee_id], date
        )
        
        # Only override if new status has higher priority
        if self._should_override_status(existing_status, status):
            self.attendance_data[employee_id][date] = [
                {"status": status, "color": color}
            ]
    
    def _add_sundays(self):
        """
        Add OFF status for Sundays without entries.
        OPTIMIZATION: Sundays pre-computed in __init__.
        """
        for employee_id in self.attendance_data.keys():
            for sunday in self.sundays:
                if not self.attendance_data[employee_id][sunday]:
                    self.attendance_data[employee_id][sunday] = [
                        {"status": "OFF", "color": "#CCCCCC"}
                    ]
    
    def _apply_saturday_lwp_rule(self):
        """
        If Saturday is LWP → Sunday must also be LWP (using priority rules).
        OPTIMIZATION: Use list() to avoid RuntimeError from dict mutation during iteration.
        """
        for employee_id, employee_data in self.attendance_data.items():
            for date, status_list in list(employee_data.items()):
                
                # Check if it's Saturday
                if date.weekday() == 5:
                    saturday_status = status_list[0]["status"]

                    # Only apply the rule if Saturday is LWP
                    if saturday_status == "LWP":
                        sunday = date + timedelta(days=1)

                        # Sunday must be within range
                        if sunday in employee_data:
                            sunday_status = employee_data[sunday][0]["status"]

                            # Only apply if LWP has higher priority than current Sunday status
                            if self._should_override_status(sunday_status, "LWP"):
                                self._set_status(
                                    employee_id,
                                    sunday,
                                    "LWP",
                                    "#a2a2a2"
                                )

    def _apply_smart_sunday_logic(self):
        """
        Replace OFF with A when person is regularly absent.
        OPTIMIZATION: Iterate dates once instead of nested loops.
        """
        for employee_id, employee_data in self.attendance_data.items():
            current_date = self.start_date
            
            while current_date <= self.end_date:
                if (current_date.weekday() == 6 and 
                    self._get_status_for_date(employee_data, current_date) == "OFF"):
                    
                    prev_status = self._get_nearby_status(
                        employee_data, current_date, direction=-1
                    )
                    next_status = self._get_nearby_status(
                        employee_data, current_date, direction=1
                    )
                    
                    if self._should_mark_absent(prev_status, next_status):
                        self._set_status(
                            employee_id, current_date, "A", "#FF0000"
                        )
                
                current_date += timedelta(days=1)
    
    def _get_nearby_status(self, employee_data, date, direction=-1, max_days=7):
        """Get status from nearby working days"""
        step = -1 if direction == -1 else 1
        check_date = date + timedelta(days=step)
        days_checked = 0
        
        while (self.start_date <= check_date <= self.end_date and 
               days_checked < max_days):
            if check_date.weekday() != 6:
                status = self._get_status_for_date(employee_data, check_date)
                if status != "OFF":
                    return status
            check_date += timedelta(days=step)
            days_checked += 1
        
        return None
    
    def _should_mark_absent(self, prev_status, next_status):
        """Determine if Sunday should be marked absent"""
        if not prev_status and not next_status:
            return False
        
        # Both sides absent
        if (prev_status and next_status and
            prev_status in self.ABSENT_STATUSES and 
            next_status in self.ABSENT_STATUSES):
            return True
        
        # One side present, other absent
        has_absent = (
            (prev_status in self.ABSENT_STATUSES) or
            (next_status in self.ABSENT_STATUSES)
        )
        has_present = (
            (prev_status in self.WORKING_STATUSES) or
            (next_status in self.WORKING_STATUSES)
        )
        
        return has_absent and not has_present
    
    def _get_office_closures(self):
        """
        Cache office closures for the date range.
        OPTIMIZATION: Called once and cached in map_attendance_data.
        """
        from ..models import OfficeClosure
        
        closures = OfficeClosure.objects.filter(
            date__range=[self.start_date, self.end_date]
        ).values_list("date", flat=True)
        
        return set(closures)
    
# Optimized aggregation function
def aggregate_attendance_data(employee_ids, start_date_object, end_date_object):
    """Simplified wrapper using the optimized mapper"""
    
    # Fetch all data at once with optimizations
    holidays = get_holiday_logs(start_date_object, end_date_object, employee_ids)
    attendance_logs = get_attendance_logs(employee_ids, start_date_object, end_date_object)
    tour_logs = get_tour_logs(employee_ids, start_date_object, end_date_object)
    leave_logs = get_leave_logs(employee_ids, start_date_object, end_date_object)
    
    # Use optimized mapper
    mapper = AttendanceMapper(start_date_object, end_date_object)
    return mapper.map_attendance_data(attendance_logs, leave_logs, holidays, tour_logs)


def get_holiday_logs(start_date, end_date, employee_ids=None):
    """Optimized holiday query with prefetch"""
    from django.db.models import Prefetch
    
    holidays = Holiday.objects.filter(
        start_date__lte=end_date,
        end_date__gte=start_date
    ).prefetch_related(
        Prefetch('applicable_users')
    )
    
    if employee_ids:
        holidays = holidays.annotate(
            user_count=Count('applicable_users')
        ).filter(
            Q(user_count=0) | Q(applicable_users__id__in=employee_ids)
        ).distinct()
    
    return holidays


def get_attendance_logs(employee_ids, start_date, end_date):
    """Optimized with select_related"""
    return AttendanceLog.objects.filter(
        applied_by_id__in=employee_ids,
        start_date__date__range=[start_date, end_date]
    ).select_related('applied_by')


def get_leave_logs(employee_ids, start_date, end_date):
    """Optimized with prefetch"""
    return LeaveDay.objects.filter(
        leave_application__appliedBy_id__in=employee_ids,
        date__range=[start_date, end_date],
        leave_application__status=settings.APPROVED
    ).select_related(
        'leave_application',
        'leave_application__leave_type',
        'leave_application__appliedBy'
    )


def get_tour_logs(employee_ids, start_date, end_date):
    """Optimized with select_related"""
    return UserTour.objects.filter(
        applied_by_id__in=employee_ids,
        start_date__range=[start_date, end_date],
        status=settings.APPROVED
    ).select_related('applied_by')


def get_days_in_month(start_date, end_date):
    """Unchanged utility"""
    return [
        start_date + timedelta(days=i) 
        for i in range((end_date - start_date).days + 1)
    ]