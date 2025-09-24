from datetime import datetime
from hrms_app.models import DeviceInformation
from hrms_app.hrms.utils import call_soap_api
from django.contrib.auth import get_user_model
from collections import defaultdict
from django.conf import settings
from django.utils.translation import gettext_lazy as _

User = get_user_model()
from django.utils.timezone import make_aware, localtime, utc
from datetime import datetime, timedelta
from hrms_app.utility.report_utils import *


def get_check_in_out_times(user):
    # Validate user info
    if not hasattr(user, 'device_location') or not hasattr(user, 'personal_detail'):
        return None, None

    office_location = user.device_location
    emp_detail = getattr(user, 'personal_detail', None)
    emp_code = getattr(emp_detail, 'employee_code', None)

    if not office_location or not emp_code:
        return None, None

    # Get device instance
    device_instance = DeviceInformation.objects.filter(
        device_location=office_location
    ).first()

    if not device_instance:
        return None, None

    # Prepare date range
    today = datetime.now().date()
    from_date = f"{today} 00:01"
    to_date = f"{today} 23:59"

    # Call SOAP API
    result = call_soap_api(
        device_instance=device_instance, from_date=from_date, to_date=to_date
    )

    if not result or emp_code not in result:
        return None, None

    emp_data = result.get(emp_code, {})
    emp_result = emp_data.get(today)

    if not emp_result or not isinstance(emp_result, list):
        return None, None

    # Extract login/logout
    login_time = emp_result[0]
    logout_time = emp_result[-1] if len(emp_result) > 1 else None

    return login_time, logout_time



def get_from_to_datetime():
    """Returns from_datetime (21st of previous month) and to_datetime (20th of current month)."""
    today = datetime.today()
    # Calculate from_datetime: 21st of previous month
    first_of_this_month = today.replace(day=1)
    from_datetime = (first_of_this_month - timedelta(days=1)).replace(day=21)
    # Calculate to_datetime: 20th of current month
    to_datetime = today.replace(day=20)
    return from_datetime, to_datetime

def get_month_start_end():
    today = datetime.today()
    
    # Start of the month is always day 1
    start_date = today.replace(day=1)

    # To get the last day, go to the next month, then subtract a day
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    
    end_date = next_month - timedelta(days=1)

    return start_date, end_date


# def map_attendance_data(
#     attendance_logs,
#     leave_logs,
#     holidays,
#     tour_logs,
#     start_date_object,
#     end_date_object,
# ):
#     attendance_data = defaultdict(lambda: defaultdict(list))
#     total_days = (end_date_object - start_date_object).days + 1
#     sundays = {
#         start_date_object + timedelta(days=i)
#         for i in range(total_days)
#         if (start_date_object + timedelta(days=i)).weekday() == 6
#     }

#     # Map holidays by date
#     holiday_days = {
#         holiday.start_date: {
#             "status": holiday.short_code,
#             "color": holiday.color_hex,
#         }
#         for holiday in holidays
#     }

#     # Keep track of which employees have tours on which dates
#     employee_tour_dates = defaultdict(set)

#     # Process attendance logs
#     for log in attendance_logs:
#         employee_id = log.applied_by.id
#         log_date = localtime(log.start_date).date()
#         office_closer = OfficeClosure.objects.filter(date=log_date).values("short_code").first()
#         if office_closer:
#             attendance_data[employee_id][log_date] = [
#                 {
#                     "status": "P",
#                     "color": "#000000",
#                 }
#             ]
#         else:
#             attendance_data[employee_id][log_date] = [
#                 {
#                     "status": log.att_status_short_code,
#                     "color": log.color_hex or "#000000",
#                 }
#             ]

#     # Process tour logs
#     for log in tour_logs:
#         daily_durations = calculate_daily_tour_durations(
#             log.start_date, log.start_time, log.end_date, log.end_time
#         )
#         for date, short_code, _ in daily_durations:
#             employee_id = log.applied_by.id
#             attendance_data[employee_id][date] = [
#                 {
#                     "status": short_code,
#                     "color": "#06c1c4",
#                 }
#             ]
#             # Track that this employee has a tour on this date
#             employee_tour_dates[employee_id].add(date)

#     # Add holidays to attendance data (but skip dates where employee has tour)
#     for employee_id, employee_data in attendance_data.items():
#         for holiday_date, holiday_info in holiday_days.items():
#             # Only add holiday if this employee doesn't have a tour on this date
#             if holiday_date not in employee_tour_dates[employee_id]:
#                 employee_data[holiday_date] = [holiday_info]

#     # Process leave logs
#     for log in leave_logs:
#         employee_id = log.leave_application.appliedBy.id
#         log_date = log.date
#         leave_type = log.leave_application.leave_type
#         leave_status = leave_type.leave_type_short_code
#         half_status = leave_type.half_day_short_code

#         # Handle "CL" leave type
#         if leave_status == "CL":
#             if log_date in holiday_days:
#                 # If FL already exists, retain it
#                 existing_status = attendance_data[employee_id].get(log_date, [])
#                 if any(entry.get("status") == "FL" for entry in existing_status):
#                     attendance_data[employee_id][
#                         log_date
#                     ] = existing_status  # Retain FL
#                 else:
#                     attendance_data[employee_id][log_date] = [
#                         {
#                             "status": "",
#                             "color": holiday_days[log_date]["color"],
#                         }
#                     ]
#             elif log_date.weekday() == 6:  # Sunday
#                 # If OFF is already set, retain it
#                 existing_status = attendance_data[employee_id].get(log_date, [])
#                 if any(entry.get("status") == "OFF" for entry in existing_status):
#                     attendance_data[employee_id][
#                         log_date
#                     ] = existing_status  # Retain OFF
#                 else:
#                     attendance_data[employee_id][log_date] = [
#                         {
#                             "status": "OFF",
#                             "color": "#CCCCCC",
#                         }
#                     ]
#             else:
#                 attendance_data[employee_id][log_date] = [
#                     {
#                         "status": leave_status if log.is_full_day else half_status,
#                         "color": leave_type.color_hex or "#FF0000",
#                     }
#                 ]
#         else:
#             # Handle other leave types
#             if any(
#                 entry.get("status") == "FL"
#                 for entry in attendance_data[employee_id].get(log_date, [])
#             ):
#                 attendance_data[employee_id][log_date] = []  # Clear the list

#             attendance_data[employee_id][log_date] = [
#                 {
#                     "status": leave_status if log.is_full_day else half_status,
#                     "color": leave_type.color_hex or "#FF0000",
#                 }
#             ]

#     # Add "OFF" status for Sundays without any entries
#     for employee_id in attendance_data.keys():
#         for sunday in sundays:
#             if not attendance_data[employee_id][sunday.date()]:
#                 attendance_data[employee_id][sunday.date()] = [
#                     {
#                         "status": "OFF",
#                         "color": "#CCCCCC",  # Default color for "OFF"
#                     }
#                 ]

#     return attendance_data

def map_attendance_data(
    attendance_logs,
    leave_logs,
    holidays,
    tour_logs,
    start_date_object,
    end_date_object,
):
    attendance_data = defaultdict(lambda: defaultdict(list))
    total_days = (end_date_object - start_date_object).days + 1
    sundays = {
        start_date_object + timedelta(days=i)
        for i in range(total_days)
        if (start_date_object + timedelta(days=i)).weekday() == 6
    }

    # Map holidays by date
    holiday_days = {
        holiday.start_date: {
            "status": holiday.short_code,
            "color": holiday.color_hex,
        }
        for holiday in holidays
    }

    # Keep track of which employees have tours on which dates
    employee_tour_dates = defaultdict(set)

    # Process attendance logs
    for log in attendance_logs:
        employee_id = log.applied_by.id
        log_date = localtime(log.start_date).date()
        office_closer = OfficeClosure.objects.filter(date=log_date).values("short_code").first()
        if office_closer:
            attendance_data[employee_id][log_date] = [
                {
                    "status": "P",
                    "color": "#000000",
                }
            ]
        else:
            attendance_data[employee_id][log_date] = [
                {
                    "status": log.att_status_short_code,
                    "color": log.color_hex or "#000000",
                }
            ]

    # Process tour logs
    for log in tour_logs:
        daily_durations = calculate_daily_tour_durations(
            log.start_date, log.start_time, log.end_date, log.end_time
        )
        for date, short_code, _ in daily_durations:
            employee_id = log.applied_by.id
            attendance_data[employee_id][date] = [
                {
                    "status": short_code,
                    "color": "#06c1c4",
                }
            ]
            # Track that this employee has a tour on this date
            employee_tour_dates[employee_id].add(date)

    # Add holidays to attendance data (but skip dates where employee has tour)
    for employee_id, employee_data in attendance_data.items():
        for holiday_date, holiday_info in holiday_days.items():
            # Only add holiday if this employee doesn't have a tour on this date
            if holiday_date not in employee_tour_dates[employee_id]:
                employee_data[holiday_date] = [holiday_info]

    # Process leave logs
    for log in leave_logs:
        employee_id = log.leave_application.appliedBy.id
        log_date = log.date
        leave_type = log.leave_application.leave_type
        leave_status = leave_type.leave_type_short_code
        half_status = leave_type.half_day_short_code

        # Handle "CL" leave type
        if leave_status == "CL":
            if log_date in holiday_days:
                # If FL already exists, retain it
                existing_status = attendance_data[employee_id].get(log_date, [])
                if any(entry.get("status") == "FL" for entry in existing_status):
                    attendance_data[employee_id][
                        log_date
                    ] = existing_status  # Retain FL
                else:
                    attendance_data[employee_id][log_date] = [
                        {
                            "status": "",
                            "color": holiday_days[log_date]["color"],
                        }
                    ]
            elif log_date.weekday() == 6:  # Sunday
                # If OFF is already set, retain it
                existing_status = attendance_data[employee_id].get(log_date, [])
                if any(entry.get("status") == "OFF" for entry in existing_status):
                    attendance_data[employee_id][
                        log_date
                    ] = existing_status  # Retain OFF
                else:
                    attendance_data[employee_id][log_date] = [
                        {
                            "status": "OFF",
                            "color": "#CCCCCC",
                        }
                    ]
            else:
                attendance_data[employee_id][log_date] = [
                    {
                        "status": leave_status if log.is_full_day else half_status,
                        "color": leave_type.color_hex or "#FF0000",
                    }
                ]
        else:
            # Handle other leave types
            if any(
                entry.get("status") == "FL"
                for entry in attendance_data[employee_id].get(log_date, [])
            ):
                attendance_data[employee_id][log_date] = []  # Clear the list

            attendance_data[employee_id][log_date] = [
                {
                    "status": leave_status if log.is_full_day else half_status,
                    "color": leave_type.color_hex or "#FF0000",
                }
            ]

    # Add "OFF" status for Sundays without any entries (initially)
    for employee_id in attendance_data.keys():
        for sunday in sundays:
            if not attendance_data[employee_id][sunday.date()]:
                attendance_data[employee_id][sunday.date()] = [
                    {
                        "status": "OFF",
                        "color": "#CCCCCC",  # Default color for "OFF"
                    }
                ]

    # Apply smart Sunday logic - replace OFF with A when person is regularly absent
    _apply_smart_sunday_logic(attendance_data, start_date_object, end_date_object)

    return attendance_data


def _apply_smart_sunday_logic(attendance_data, start_date_object, end_date_object):
    """
    Apply smart Sunday logic:
    - Keep OFF only when Sunday falls between working days (P, tours, leaves)
    - Replace OFF with A when person is regularly absent
    """
    
    def _get_status_for_date(employee_data, date):
        """Get the primary status for a given date"""
        if date not in employee_data or not employee_data[date]:
            return "A"  # No entry means absent
        
        status = employee_data[date][0].get("status", "A")
        return status if status else "A"
    
    def _is_working_status(status):
        """Check if status indicates person was working/present"""
        working_statuses = {"P", "L", "CL", "SL", "ML", "EL", "FL", "H", "T"}  # Add your leave codes
        return status in working_statuses
    
    def _is_absent_status(status):
        """Check if status indicates absence"""
        absent_statuses = {"A", "LWP", "AWOL"}  # Add your absent status codes
        return status in absent_statuses
    
    # Process each employee
    for employee_id, employee_data in attendance_data.items():
        # Get all dates in chronological order
        current_date = start_date_object
        
        while current_date <= end_date_object:
            # Check if current date is Sunday and has OFF status
            if (current_date.weekday() == 6 and 
                current_date in employee_data and 
                _get_status_for_date(employee_data, current_date) == "OFF"):
                
                # Find previous working day status
                prev_working_status = None
                check_date = current_date - timedelta(days=1)
                days_checked = 0
                
                while check_date >= start_date_object and days_checked < 7:  # Look back max 7 days
                    if check_date.weekday() != 6:  # Skip other Sundays
                        status = _get_status_for_date(employee_data, check_date)
                        if status != "OFF":  # Found a non-Sunday status
                            prev_working_status = status
                            break
                    check_date -= timedelta(days=1)
                    days_checked += 1
                
                # Find next working day status
                next_working_status = None
                check_date = current_date + timedelta(days=1)
                days_checked = 0
                
                while check_date <= end_date_object and days_checked < 7:  # Look ahead max 7 days
                    if check_date.weekday() != 6:  # Skip other Sundays
                        status = _get_status_for_date(employee_data, check_date)
                        if status != "OFF":  # Found a non-Sunday status
                            next_working_status = status
                            break
                    check_date += timedelta(days=1)
                    days_checked += 1
                
                # Apply the logic
                should_change_to_absent = False
                
                # Case 1: Both previous and next are absent
                if (prev_working_status and next_working_status and 
                    _is_absent_status(prev_working_status) and _is_absent_status(next_working_status)):
                    should_change_to_absent = True
                
                # Case 2: Previous is absent and next is working (or no next)
                elif (prev_working_status and _is_absent_status(prev_working_status) and 
                      (not next_working_status or _is_working_status(next_working_status))):
                    should_change_to_absent = True
                
                # Case 3: Previous is working and next is absent (or no previous)  
                elif (next_working_status and _is_absent_status(next_working_status) and 
                      (not prev_working_status or _is_working_status(prev_working_status))):
                    should_change_to_absent = True
                
                # Case 4: Only one side has data and it's absent
                elif ((prev_working_status and not next_working_status and _is_absent_status(prev_working_status)) or
                      (next_working_status and not prev_working_status and _is_absent_status(next_working_status))):
                    should_change_to_absent = True
                
                # Case 5: Check for continuous absence pattern (more comprehensive)
                elif _is_continuous_absence_pattern(employee_data, current_date, start_date_object, end_date_object):
                    should_change_to_absent = True
                
                # Change Sunday from OFF to A if conditions met
                if should_change_to_absent:
                    employee_data[current_date] = [
                        {
                            "status": "A",
                            "color": "#FF0000",  # Red color for absent
                        }
                    ]
            
            current_date += timedelta(days=1)


def _is_continuous_absence_pattern(employee_data, sunday_date, start_date_object, end_date_object):
    """
    Check if Sunday falls within a continuous absence pattern
    Returns True if there are more absent days than working days in the surrounding week
    """
    
    def _get_status_for_date(date):
        if date not in employee_data or not employee_data[date]:
            return "A"
        status = employee_data[date][0].get("status", "A")
        return status if status else "A"
    
    def _is_absent_status(status):
        absent_statuses = {"A", "LWP", "AWOL"}
        return status in absent_statuses
    
    # Check 3 days before and 3 days after Sunday (excluding other Sundays)
    absent_count = 0
    working_count = 0
    
    for i in range(-3, 4):  # -3 to +3 days around Sunday
        check_date = sunday_date + timedelta(days=i)
        
        # Skip the Sunday itself and other Sundays, and dates outside range
        if (check_date == sunday_date or 
            check_date.weekday() == 6 or
            check_date < start_date_object or 
            check_date > end_date_object):
            continue
            
        status = _get_status_for_date(check_date)
        
        if _is_absent_status(status):
            absent_count += 1
        elif status not in ["OFF"]:  # Count non-OFF statuses as working
            working_count += 1
    
    # If more absent days than working days, consider it continuous absence
    return absent_count > working_count and absent_count >= 2

def aggregate_attendance_data(
    employee_ids,
    start_date_object,
    end_date_object,
):
    attendance_data = defaultdict(lambda: defaultdict(list))
    total_days = (end_date_object - start_date_object).days + 1
    sundays = {
        start_date_object + timedelta(days=i)
        for i in range(total_days)
        if (start_date_object + timedelta(days=i)).weekday() == 6
    }
    holidays = get_holiday_logs(start_date=start_date_object,end_date=end_date_object)
    attendance_logs = get_attendance_logs(employee_ids=employee_ids,start_date=start_date_object,end_date=end_date_object)
    tour_logs = get_tour_logs(employee_ids=employee_ids,start_date=start_date_object,end_date=end_date_object)
    leave_logs = get_leave_logs(employee_ids=employee_ids,start_date=start_date_object,end_date=end_date_object)
    # Map holidays by date
    holiday_days = {
        holiday.start_date: {
            "status": holiday.short_code,
            "color": holiday.color_hex,
        }
        for holiday in holidays
    }

    # Process attendance logs
    for log in attendance_logs:
        employee_id = log.applied_by.username
        log_date = localtime(log.start_date).date()
        office_closer = OfficeClosure.objects.filter(date=log_date).values("short_code").first()
        if office_closer:
            attendance_data[employee_id][log_date] = [
                {
                    "status": "P",
                    "color": "#000000",
                }
            ]
        else:
            attendance_data[employee_id][log_date] = [
                {
                    "status": log.att_status_short_code,
                    "color": log.color_hex or "#000000",
                }
            ]

    # Process tour logs
    for log in tour_logs:
        daily_durations = calculate_daily_tour_durations(
            log.start_date, log.start_time, log.end_date, log.end_time
        )
        for date, short_code, _ in daily_durations:
            employee_id = log.applied_by.username
            attendance_data[employee_id][date] = [
                {
                    "status": short_code,
                    "color": "#06c1c4",
                }
            ]
            holiday_days.pop(date, None)

    # Add holidays to attendance data
    for employee_id, employee_data in attendance_data.items():
        for holiday_date, holiday_info in holiday_days.items():
            employee_data[holiday_date] = [holiday_info]

    # Process leave logs
    for log in leave_logs:
        employee_id = log.leave_application.appliedBy.username
        log_date = log.date
        leave_type = log.leave_application.leave_type
        leave_status = leave_type.leave_type_short_code
        half_status = leave_type.half_day_short_code

        # Handle "CL" leave type
        # Handle "CL" leave type
        if leave_status == "CL":
            if log_date in holiday_days:
                # If FL already exists, retain it
                existing_status = attendance_data[employee_id].get(log_date, [])
                if any(entry.get("status") == "FL" for entry in existing_status):
                    attendance_data[employee_id][
                        log_date
                    ] = existing_status  # Retain FL
                else:
                    attendance_data[employee_id][log_date] = [
                        {
                            "status": "",
                            "color": holiday_days[log_date]["color"],
                        }
                    ]
            elif log_date.weekday() == 6:  # Sunday
                # If OFF is already set, retain it
                existing_status = attendance_data[employee_id].get(log_date, [])
                if any(entry.get("status") == "OFF" for entry in existing_status):
                    attendance_data[employee_id][
                        log_date
                    ] = existing_status  # Retain OFF
                else:
                    attendance_data[employee_id][log_date] = [
                        {
                            "status": "OFF",
                            "color": "#CCCCCC",
                        }
                    ]
            else:
                attendance_data[employee_id][log_date] = [
                    {
                        "status": leave_status if log.is_full_day else half_status,
                        "color": leave_type.color_hex or "#FF0000",
                    }
                ]
        else:
            # Handle other leave types
            if any(
                entry.get("status") == "FL"
                for entry in attendance_data[employee_id].get(log_date, [])
            ):
                attendance_data[employee_id][log_date] = []  # Clear the list

            attendance_data[employee_id][log_date] = [
                {
                    "status": leave_status if log.is_full_day else half_status,
                    "color": leave_type.color_hex or "#FF0000",
                }
            ]

    # Add "OFF" status for Sundays without any entries
    for employee_id in attendance_data.keys():
        for sunday in sundays:
            if not attendance_data[employee_id][sunday.date()]:
                attendance_data[employee_id][sunday.date()] = [
                    {
                        "status": "OFF",
                        "color": "#CCCCCC",  # Default color for "OFF"
                    }
                ]

    return attendance_data



def get_days_in_month(start_date, end_date):
    return [
        start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)
    ]


def get_holiday_logs(start_date, end_date):
    return Holiday.objects.filter(start_date__range=[start_date, end_date])


def get_attendance_logs(employee_ids, start_date, end_date):
    return AttendanceLog.objects.filter(
        applied_by_id__in=employee_ids, start_date__date__range=[start_date, end_date]
    )


def get_leave_logs(employee_ids, start_date=None, end_date=None):
    return LeaveDay.objects.filter(
        leave_application__appliedBy_id__in=employee_ids,
        date__range=[start_date, end_date],
        leave_application__status=settings.APPROVED,
    )


def get_tour_logs(employee_ids, start_date, end_date):
    return UserTour.objects.filter(
        applied_by_id__in=employee_ids,
        start_date__range=[start_date, end_date],
        status=settings.APPROVED,
    )


def str_to_date(value):
    from django.utils.timezone import localtime, make_aware, utc
    date_time = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    date_time = (
        make_aware(date_time, timezone=utc) if date_time.tzinfo is None else date_time
    )
    return date_time
