from django.contrib.auth import get_user_model
from collections import defaultdict
from django.utils.translation import gettext_lazy as _
from django.db.models import Prefetch,Q
from hrms_app.models import (
    AttendanceLog,
    LeaveDay,
    UserTour,
    OfficeClosure,
)
from django.utils.timezone import localtime
from datetime import datetime, timedelta
from django.conf import settings

User = get_user_model()

def get_monthly_presence_html_table(
    converted_from_datetime, converted_to_datetime, is_active, location, query
):
    monthly_presence_data = generate_monthly_presence_data_detailed(
        converted_from_datetime, converted_to_datetime, is_active, location, query
    )
    date_range = [
        (converted_from_datetime + timedelta(days=day))
        for day in range((converted_to_datetime - converted_from_datetime).days + 1)
    ]

    # HTML table construction
    headers = ["Employee Code", "Name", "Attendance"] + [
        f"{day.day}-{day.strftime('%b')}" for day in date_range
    ]
    table_html = (
        '<div class="table-container"><table class="rtable table-bordered">'
        "<thead><tr>"
        + "".join(f'<th class="sticky-header">{header}</th>' for header in headers)
        + "</tr></thead><tbody>"
    )
    users = User.objects.filter(is_active=is_active).select_related("personal_detail")
    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
        )

    for user in users:
        emp_code = user.personal_detail.employee_code
        if emp_code in monthly_presence_data:
            row_data = {
                "status": f'<tr><td class="sticky-col" rowspan="7">KMPCL-{format_emp_code(emp_code)}</td><td class="sticky-col" rowspan="7">{user.get_full_name()}</td><td>Status</td>',
                "in_time": "<tr><td>In Time</td>",
                "out_time": "<tr><td>Out Time</td>",
                "total_duration": "<tr><td>Duration</td>",
                "leave": "<tr><td>Leave</td>",
                "tour": "<tr><td>Tour</td>",
                "reg": "<tr><td>Reg</td>",
            }

            for day_date in date_range:
                day_str = day_date.strftime("%Y-%m-%d")
                cell_data = get_cell_data(
                    user, day_date, day_str, monthly_presence_data, emp_code
                )
                for row_type in row_data.keys():
                    style = get_style(row_type, cell_data)
                    row_data[
                        row_type
                    ] += f'<td class="{style}">{cell_data[row_type]}</td>'

            for row in row_data.values():
                table_html += row + "</tr>"
            table_html += "<tr></tr>"

    table_html += "</tbody></table></div>"
    return table_html


def generate_monthly_presence_data_detailed(
    converted_from_datetime, converted_to_datetime, is_active, location, query
):
    monthly_presence_data = defaultdict(lambda: defaultdict(dict))
    
    # OPTIMIZATION: Build employee filter once and reuse
    employees_filter = Q(is_active=is_active)
    if query:
        employees_filter &= (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
        )
    if location:
        employees_filter &= Q(device_location__in=location.values_list("id", flat=True))
    
    employees = (
        User.objects.filter(employees_filter)
        .prefetch_related(Prefetch("personal_detail", to_attr="personal_detail_cache"))
        .order_by("first_name")
    )
    
    # OPTIMIZATION: Get employee IDs once for all subsequent queries
    employee_ids = list(employees.values_list("id", flat=True))
    
    # OPTIMIZATION: Build date range filter once
    date_range_filter = (
        Q(
            leave_application__startDate__date__range=[
                converted_from_datetime,
                converted_to_datetime,
            ]
        )
        | Q(
            leave_application__endDate__date__range=[
                converted_from_datetime,
                converted_to_datetime,
            ]
        )
        | Q(
            leave_application__startDate__date__lte=converted_from_datetime,
            leave_application__endDate__date__gte=converted_to_datetime,
        )
    )
    
    leaves = (
        LeaveDay.objects.filter(
            date_range_filter,
            leave_application__appliedBy__in=employee_ids,
            leave_application__status=settings.APPROVED,
        )
        .exclude(leave_application__leave_type__leave_type_short_code="STL")
        .select_related(
            "leave_application__appliedBy__personal_detail",
            "leave_application__leave_type"  # OPTIMIZATION: Prefetch leave_type
        )
    )
    
    logs = (
        AttendanceLog.objects.filter(
            Q(start_date__date__range=[converted_from_datetime, converted_to_datetime])
            | Q(end_date__date__range=[converted_from_datetime, converted_to_datetime]),
            applied_by__in=employee_ids,
        )
        .select_related("applied_by__personal_detail")
        .order_by("applied_by_id", "start_date")  # OPTIMIZATION: Order for better cache locality
    )
    
    all_tours = (
        UserTour.objects.filter(
            Q(start_date__range=[converted_from_datetime, converted_to_datetime])
            | Q(end_date__range=[converted_from_datetime, converted_to_datetime])
            | Q(
                start_date__lte=converted_from_datetime,
                end_date__gte=converted_to_datetime,
            ),
            applied_by__in=employee_ids,
            status=settings.APPROVED,
        )
        .select_related("applied_by__personal_detail")
        .order_by("applied_by_id")  # OPTIMIZATION: Order for better cache locality
    )
    
    from .attendance_mapper import get_holiday_logs
    
    holidays = get_holiday_logs(converted_from_datetime, converted_to_datetime)

    process_sundays_and_holidays(
        employees,
        holidays,
        monthly_presence_data,
        converted_from_datetime,
        converted_to_datetime,
    )
    
    process_logs(logs, monthly_presence_data, converted_from_datetime, converted_to_datetime)
    process_leaves(leaves, monthly_presence_data)
    process_tours(all_tours, monthly_presence_data)

    return monthly_presence_data


def process_sundays_and_holidays(
    employees,
    holidays,
    monthly_presence_data,
    converted_from_datetime,
    converted_to_datetime,
):
    # OPTIMIZATION: Pre-calculate total days once
    total_days = (converted_to_datetime - converted_from_datetime).days + 1
    
    # -------------------------
    # 1️⃣ Identify all Sundays
    # -------------------------
    sundays = {
        (converted_from_datetime + timedelta(days=day)).strftime("%Y-%m-%d")
        for day in range(total_days)
        if (converted_from_datetime + timedelta(days=day)).weekday() == 6
    }

    # -------------------------
    # 2️⃣ Preload holiday applicability
    # -------------------------
    holiday_map = {}  # {holiday_date: (holiday_obj, set(applicable_user_ids) or None)}

    for holiday in holidays:
        holiday_date = holiday.start_date.strftime("%Y-%m-%d")

        # OPTIMIZATION: Use set for O(1) membership checks instead of list
        applicable_users = set(
            holiday.applicable_users.values_list("id", flat=True)
        )

        # If empty -> applies to everyone
        holiday_map[holiday_date] = (
            holiday,
            applicable_users if applicable_users else None
        )

    # -------------------------
    # 3️⃣ Apply Sunday + Holidays employee wise
    # -------------------------
    for employee in employees:
        emp_code = employee.personal_detail_cache.employee_code
        emp_id = employee.id

        # ----- Sundays (global OFF unless already filled) -----
        for sunday in sundays:
            if sunday not in monthly_presence_data[emp_code]:
                monthly_presence_data[emp_code][sunday]["sunday"] = {
                    "status": "OFF",
                    "in_time": None,
                    "out_time": None,
                    "total_duration": None,
                }

        # ----- Holidays (user-specific) -----
        for holiday_date, (holiday, applicable_users) in holiday_map.items():

            # OPTIMIZATION: Use set membership check (O(1) instead of O(n))
            # only apply if: applicable_users is None OR emp_id is in applicable_users
            if applicable_users is None or emp_id in applicable_users:

                if holiday_date not in monthly_presence_data[emp_code]:
                    monthly_presence_data[emp_code][holiday_date]["holiday"] = {
                        "status": holiday.short_code,
                        "in_time": None,
                        "out_time": None,
                        "total_duration": None,
                    }


def process_logs(logs, monthly_presence_data, converted_from_datetime, converted_to_datetime):
    # OPTIMIZATION: Batch fetch all office closures and STL leaves upfront to eliminate N+1 queries
    date_range_days = (converted_to_datetime - converted_from_datetime).days + 1
    all_dates = [
        converted_from_datetime + timedelta(days=day)
        for day in range(date_range_days)
    ]
    
    # OPTIMIZATION: Build office closure map once
    office_closures = OfficeClosure.objects.filter(
        date__in=[d for d in all_dates]
    ).values("date", "short_code")
    office_closure_map = {
        oc["date"]: oc["short_code"] for oc in office_closures
    }
    
    # OPTIMIZATION: Build STL leave map once (grouped by employee and date)
    stl_leaves = (
        LeaveDay.objects
        .approved()
        .filter(
            date__range=[converted_from_datetime, converted_to_datetime],
            leave_application__leave_type__leave_type_short_code="STL",
        )
        .select_related("leave_application__appliedBy", "leave_application")
        .values(
            "date",
            "leave_application__appliedBy_id",
            "leave_application__from_time",
            "leave_application__to_time",
        )
    )
    
    # OPTIMIZATION: Create lookup dict for O(1) access
    stl_map = {}
    for stl in stl_leaves:
        key = (stl["leave_application__appliedBy_id"], stl["date"])
        stl_map[key] = {
            "from_time": stl["leave_application__from_time"],
            "to_time": stl["leave_application__to_time"],
        }
    
    for log in logs:
        emp_code = log.applied_by.personal_detail.employee_code
        log_date = log.start_date.date()
        date_key = log_date.strftime("%Y-%m-%d")

        # -----------------------------
        # Attendance data (UNCHANGED)
        # -----------------------------
        in_time = localtime(log.start_date).strftime("%I:%M")
        out_time = localtime(log.end_date).strftime("%I:%M")
        status = log.att_status_short_code
        duration = log.duration

        # -----------------------------
        # Office Closure (REG row) - OPTIMIZED with pre-built map
        # -----------------------------
        reg_value = office_closure_map.get(log_date, "")

        # -----------------------------
        # STL (REG row ONLY) - OPTIMIZED with pre-built map
        # -----------------------------
        stl_data = stl_map.get((log.applied_by.id, log_date))
        
        if stl_data:
            from_time = stl_data["from_time"]
            to_time = stl_data["to_time"]

            if from_time and to_time:
                stl_duration = (
                    datetime.combine(log_date, to_time)
                    - datetime.combine(log_date, from_time)
                )
                reg_value = (
                    f"STL "
                    f"({from_time.strftime('%H:%M')} - "
                    f"{to_time.strftime('%H:%M')}) "
                    f"[{stl_duration}]"
                )
            else:
                reg_value = "STL"

        # -----------------------------
        # Update monthly_presence_data
        # -----------------------------
        monthly_presence_data[emp_code][date_key]["present"] = {
            "status": status,
            "in_time": in_time,
            "out_time": out_time,
            "total_duration": duration,
            "reg": reg_value,
        }


def process_leaves(leaves, monthly_presence_data):
    for leave in leaves:
        emp_code = leave.leave_application.appliedBy.personal_detail.employee_code
        
        # OPTIMIZATION: Access leave_type once (already prefetched)
        leave_type = leave.leave_application.leave_type
        code = (
            leave_type.leave_type_short_code
            if leave.is_full_day
            else leave_type.half_day_short_code
        )

        employee_attendance = monthly_presence_data.get(emp_code, {})
        date_key = leave.date.strftime("%Y-%m-%d")
        current_entry = (
            employee_attendance.get(date_key, {}) if employee_attendance else None
        )

        # Remove OFF/FL only if not CL SL
        if code != "CL" or code != "SL":
            if current_entry and (
                current_entry.get("sunday", {}).get("status") == "OFF"
                or current_entry.get("holiday", {}).get("status") == "FL"
            ):
                current_entry.pop("sunday", None)
                current_entry.pop("holiday", None)

        # Ensure structure exists
        if emp_code not in monthly_presence_data:
            monthly_presence_data[emp_code] = {}
        if date_key not in monthly_presence_data[emp_code]:
            monthly_presence_data[emp_code][date_key] = {}

        # Add leave for this date
        monthly_presence_data[emp_code][date_key]["leave"] = {
            "leave": code,
            "in_time": None,
            "out_time": None,
            "total_duration": None,
        }

        # ----------------------------------------------------------
        #   ⭐ OVERRIDE SUNDAY IF SATURDAY HAS LWP (your requirement)
        # ----------------------------------------------------------
        if leave.date.weekday() == 5 and code == "LWP":
            sunday_date = (leave.date + timedelta(days=1)).strftime("%Y-%m-%d")

            # Ensure Sunday section exists
            if sunday_date not in monthly_presence_data[emp_code]:
                monthly_presence_data[emp_code][sunday_date] = {}

            # OVERRIDE SUNDAY → LWP (remove OFF or existing keys)
            monthly_presence_data[emp_code][sunday_date]["sunday"] = {
                "status": "LWP",
                "in_time": None,
                "out_time": None,
                "total_duration": None,
            }


def process_tours(all_tours, monthly_presence_data):
    for tour in all_tours:
        daily_durations = calculate_daily_tour_durations(
            tour.start_date, tour.start_time, tour.end_date, tour.end_time
        )
        emp_code = tour.applied_by.personal_detail.employee_code
        for date, short_code, duration in daily_durations:
            monthly_presence_data[emp_code][date.strftime("%Y-%m-%d")]["tour"] = {
                "tour": short_code,
                "in_time": None,
                "out_time": None,
                "total_duration": str(duration),
            }

def get_office_closers(start_date, end_date):
    """
    Fetch office closure records within a date range (inclusive),
    returning only date and short_code fields as dictionaries.
    
    Returns:
        List[Dict]: [{'date': ..., 'short_code': ...}, ...]
    """
    return list(
        OfficeClosure.objects.filter(
            date__range=(start_date, end_date)
        )
        .order_by('-date')
        .values('date', 'short_code')
    )


def calculate_daily_tour_durations(start_date, start_time, end_date, end_time):
    # Combine date and time into datetime objects
    start_datetime = datetime.combine(start_date, start_time or datetime.min.time())
    end_datetime = datetime.combine(end_date, end_time or datetime.min.time())
    # Initialize the current datetime to the start datetime
    current_datetime = start_datetime
    daily_durations = []
    while current_datetime.date() <= end_datetime.date():
        # Calculate the end of the current day
        attendance_log = AttendanceLog.objects.filter(
            start_date__date=current_datetime.date()
        ).first()
        # Initialize log duration
        log_duration = timedelta(hours=0)  # Default duration is 0
        # Add attendance log duration if it exists
        if attendance_log and attendance_log.duration:
            log_duration = timedelta(
                hours=attendance_log.duration.hour,
                minutes=attendance_log.duration.minute,
                seconds=attendance_log.duration.second,
            )
        end_of_day = datetime.combine(current_datetime.date(), datetime.max.time())
        # Determine the actual end time for the current day
        actual_end_time = min(end_of_day, end_datetime)
        # Calculate the duration for the current day
        duration = actual_end_time - current_datetime
        # Combine log duration and calculated duration
        total_duration = duration + log_duration
        total_hours = total_duration.total_seconds() / 3600
        # Determine the short code based on the total hours
        short_code = "T" if total_hours >= 8 else "TH"
        # Append the result for the current day
        daily_durations.append((current_datetime.date(), short_code, total_duration))
        # Move to the next day
        current_datetime = datetime.combine(
            current_datetime.date() + timedelta(days=1), datetime.min.time()
        )
    return daily_durations


def mark_leave_attendance(current_date, att, day_entry_start):
    if current_date == att.startDate:
        if att.endDayChoice == "1":
            return att.leave_type.leave_type_short_code

        elif att.endDayChoice == "3":
            return f"{att.leave_type.half_day_short_code}"

        elif att.endDayChoice == "2":
            return f"{att.leave_type.half_day_short_code}"

    elif current_date == att.endDate:
        if att.endDayChoice == "2":
            return f"{att.leave_type.half_day_short_code}"
        else:
            if day_entry_start == current_date:
                return "P|L"
            else:
                return att.leave_type.leave_type_short_code
    else:
        return att.leave_type.leave_type_short_code


def format_duration(total_duration):
    hours = int(total_duration)
    minutes = int((total_duration - hours) * 60)
    return f"{hours}:{minutes}"


def format_emp_code(emp_code):
    length = len(emp_code)
    if length == 1:
        return f"00{emp_code}"
    elif length == 2:
        return f"0{emp_code}"
    else:
        return emp_code

def get_cell_data(user, day_date, day_str, monthly_presence_data, emp_code):
    cell_data = {
        "status": "A",
        "in_time": "",
        "out_time": "",
        "total_duration": "",
        "leave": "",
        "tour": "",
        "reg": "",
    }
    if (
        (user.personal_detail.dot and day_date < user.personal_detail.dot)
        or (
            not user.personal_detail.dot
            and user.personal_detail.doj
            and day_date < user.personal_detail.doj
        )
        or (user.personal_detail.dol and day_date >= user.personal_detail.dol)
    ):
        return cell_data

    status_entry = monthly_presence_data.get(emp_code, {}).get(day_str, None)
    if status_entry:
        cell_data.update(
            {
                "status": status_entry.get("present", {}).get(
                    "status", cell_data["status"]
                ),
                "in_time": status_entry.get("present", {}).get("in_time", ""),
                "out_time": status_entry.get("present", {}).get("out_time", ""),
                "total_duration": status_entry.get("present", {}).get(
                    "total_duration", ""
                ),
                "leave": status_entry.get("holiday", {}).get(
                    "status", status_entry.get("leave", {}).get("leave", "")
                ),
                "tour": status_entry.get("tour", {}).get("tour", ""),
                "reg": status_entry.get("present", {}).get("reg", ""),
            }
        )
        if status_entry.get("sunday", {}).get("status"):
            cell_data["leave"] = status_entry["sunday"]["status"]
    return cell_data


def get_style(row_type, cell_data):
    if row_type == "status":
        return {
            "P": "text-success",
            "T": "text-primary",
            "A": "text-danger",
            "H": "text-secondary",
        }.get(cell_data[row_type], "text-dark")
    return ""
