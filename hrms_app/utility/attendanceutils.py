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
#             holiday_days.pop(date, None)

#     # Add holidays to attendance data
#     for employee_id, employee_data in attendance_data.items():
#         for holiday_date, holiday_info in holiday_days.items():
#             employee_data[holiday_date] = [holiday_info]

#     # Process leave logs
#     for log in leave_logs:
#         employee_id = log.leave_application.appliedBy.id
#         log_date = log.date
#         leave_type = log.leave_application.leave_type
#         leave_status = leave_type.leave_type_short_code
#         half_status = leave_type.half_day_short_code

#         # Handle "CL" leave type
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


def get_leave_logs(employee_ids, start_date, end_date):
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
