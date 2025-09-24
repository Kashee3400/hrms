from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.conf import settings
from hrms_app.utility.leave_utils import (
    get_employee_requested_leave,
    get_employee_requested_tour,
    get_regularization_requests,
)
from django.utils.translation import gettext as _
from hrms_app.utility.attendanceutils import get_from_to_datetime,get_month_start_end
from hrms_app.models import PersonalDetails
from django.utils.timezone import now, localdate, localtime
from django.db import models
from datetime import timedelta
import random
from ..models import (
    LeaveType,
    LeaveBalanceOpenings,
    LeaveApplication,
    Holiday,
    HRAnnouncement,
    AttendanceLog,
    UserTour,
)

register = template.Library()


@register.simple_tag
def render_breadcrumb(title, urls):
    """
    Render breadcrumb HTML with dynamic title and URLs using Bootstrap classes.

    :param title: Title for the breadcrumb section.
    :param urls: List of tuples containing URL name and URL kwargs.
    :return: Rendered breadcrumb HTML.
    """
    home = reverse("home")
    breadcrumb_html = f"""
    <div class="row border-bottom py-3 mb-3">
      <div class="col-md-4 d-flex align-items-center">
        <h3 class="dashboard-section-title text-center text-md-start w-100">{title}</h3>
      </div>

      <div class="col-md-8 d-flex justify-content-center justify-content-md-end align-items-center">
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb mb-0 bg-transparent">
            <li class="breadcrumb-item">
              <a href="{home}">
                <i class="mdi mdi-home"></i>
              </a>
            </li>
    """
    for url_name, url_kwargs in urls:
        url = reverse(
            url_name, kwargs={k: v for k, v in url_kwargs.items() if k != "label"}
        )
        breadcrumb_html += f"""
            <li class="breadcrumb-item">
              <a href="{url}">{url_kwargs.get('label')}</a>
            </li>
        """

    breadcrumb_html += """
          </ol>
        </nav>
      </div>
    </div>
    """
    return mark_safe(breadcrumb_html)


@register.simple_tag
def render_status_choices():
    choices = settings.STATUS_CHOICES
    options = ""
    for choice in choices:
        selected = "selected" if choice[0] == "Pending" else ""
        options += f'<option value="{choice[0]}" {selected} class="fg-{choice[0].lower()}">{choice[1]}</option>'
    return mark_safe(f'<select data-role="select">{options}</select>')


from datetime import datetime


@register.filter
def format_custom_date(value):
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y %I:%M %p").lower()
    return value


@register.simple_tag
def leave_start_end_status(choice):
    if choice == "1":
        return "Full Day"
    elif choice == "2":
        return "First Half (Morning)"
    else:
        return "Second Half (Afternoon)"


@register.inclusion_tag("notifications/leave_notification_list.html")
def load_notifications(user):
    pending_leaves = get_employee_requested_leave(user=user)
    pending_tours = get_employee_requested_tour(user=user)
    pending_reg = get_regularization_requests(user=user)
    total_counts = len(pending_leaves) + pending_tours.count() + pending_reg.count()
    return {
        "count": total_counts,
    }


@register.inclusion_tag("notifications/notification.html")
def load_side_notifications(user):
    pending_leaves = get_employee_requested_leave(user=user)
    pending_tours = get_employee_requested_tour(user=user)
    pending_reg = get_regularization_requests(user=user)
    total_counts = len(pending_leaves) + pending_tours.count() + pending_reg.count()
    return {
        "pending_leaves": pending_leaves,
        "pending_tours": pending_tours,
        "pending_reg": pending_reg,
        "count": total_counts,
    }


@register.inclusion_tag("hrms_app/navigation/navigation.html", takes_context=True)
def render_employee_navigation(context):
    request = context["request"]
    navigation_items = [
        {"name": "Employees", "url_name": "employees", "icon": "mif-lock"},
        {
            "name": "Register Employee",
            "url_name": "create_user",
            "icon": "mif-user-plus",
        },
        # Add more navigation items here
    ]

    for item in navigation_items:
        item["is_active"] = request.path == reverse(item["url_name"])

    return {
        "navigation_items": navigation_items,
        "is_parent_active": any(item["is_active"] for item in navigation_items),
    }


from django.db.models import Sum


@register.inclusion_tag("leave_balances/leave_balance_list.html")
def get_leave_balances(user, request):
    """Fetch leave balances for the user, including used leave."""
    try:
        leave_types = LeaveType.objects.all()
        leave_balances = LeaveBalanceOpenings.objects.filter(
            user=user, leave_type__in=leave_types
        )
        leave_balances_dict = {lb.leave_type: lb for lb in leave_balances}
        user_pending_leaves = LeaveApplication.objects.filter(
            appliedBy=user, status=settings.PENDING
        )

        leave_balances_list = []
        for lb in leave_balances:
            # Calculate used leave for this leave type
            used_leave = (
                LeaveApplication.objects.filter(
                    appliedBy=user, leave_type=lb.leave_type, status=settings.APPROVED
                ).aggregate(Sum("usedLeave"))["usedLeave__sum"]
                or 0
            )  # Default to 0 if None

            on_hold_leave = sum(
                leave.usedLeave
                for leave in user_pending_leaves
                if leave.leave_type == lb.leave_type
            )
            total_balance = lb.remaining_leave_balances - on_hold_leave
            leave_balances_list.append(
                {
                    "pk": lb.pk,
                    "balance": int(lb.remaining_leave_balances) if lb.leave_type.leave_type_short_code == 'EL' else lb.remaining_leave_balances,
                    "used_leave": int(used_leave) if lb.leave_type.leave_type_short_code == 'EL' else used_leave,
                    "on_hold": int(on_hold_leave) if lb.leave_type.leave_type_short_code == 'EL' else on_hold_leave,
                    "total_balance": int(total_balance) if lb.leave_type.leave_type_short_code == 'EL' else total_balance,
                    "leave_type": lb.leave_type,
                    "url": reverse("apply_leave_with_id", args=[lb.leave_type.pk]),
                    "color": lb.leave_type.color_hex,
                }
            )
        if user.personal_detail and user.personal_detail.gender.gender == "Female":
            ml_balance = leave_balances_dict.get(settings.ML)
            if ml_balance:
                used_leave = (
                    LeaveApplication.objects.filter(
                        appliedBy=user,
                        leave_type=ml_balance.leave_type,
                        status=settings.APPROVED,
                    ).aggregate(Sum("usedLeave"))["usedLeave__sum"]
                    or 0
                )
                on_hold_leave = sum(
                    leave.usedLeave
                    for leave in user_pending_leaves
                    if leave.leave_type == ml_balance.leave_type
                )
                leave_balances_list.append(
                    {
                        "pk": ml_balance.pk,
                        "balance": ml_balance.remaining_leave_balances,
                        "used_leave": used_leave,
                        "on_hold": on_hold_leave,
                        "total_balance": ml_balance.remaining_leave_balances
                        - used_leave
                        - on_hold_leave,
                        "leave_type": ml_balance.leave_type.leave_type,
                        "url": reverse(
                            "apply_leave_with_id", args=[ml_balance.leave_type.id]
                        ),
                        "color": "#ff9447",  # Special color for ML leave
                    }
                )

        return {"leave_balances": leave_balances_list, "request": request}

    except LeaveBalanceOpenings.DoesNotExist:
        return {"leave_balances": []}
    except Exception as e:
        # Log the error if necessary
        return {"leave_balances": []}


@register.simple_tag
def format_emp_code(emp_code):
    length = len(emp_code)
    if length == 1:
        return f"KMPCL-00{emp_code}"
    elif length == 2:
        return f"KMPCL-0{emp_code}"
    else:
        return f"KMPCL-{emp_code}"


@register.inclusion_tag(
    "hrms_app/components/user_summary_counts.html", takes_context=True
)
def user_summary_counts(context):
    request = context["request"]
    user = request.user
    from_datetime, to_datetime = get_month_start_end()
    total_pending_leaves = LeaveApplication.objects.filter(
        appliedBy=user,
        status=settings.PENDING,
    ).count()

    pending_regularized = AttendanceLog.objects.filter(
        applied_by=user,
        is_regularisation=True,
        is_submitted=True,
        start_date__date__gte=from_datetime.date(),
        end_date__date__lte=to_datetime.date(),
    ).count()
    
    total_pending_tour = UserTour.objects.filter(
            applied_by=user,
            status__in=[settings.PENDING,settings.EXTENDED],
        ).count()

    # Counts dict
    counts = {
        "leave": total_pending_leaves,
        "tour": total_pending_tour,
        "regularization": pending_regularized,
    }
    items = [
        {
            "key": "leave",
            "title": _("Leaves"),
            "icon": "fas fa-hourglass-half",
            "link": reverse("leave_tracker"),
        },
        {
            "key": "tour",
            "title": _("Tours"),
            "icon": "fas fa-plane-departure",
            "link": reverse("tour_tracker"),
        },
        {
            "key": "regularization",
            "title": _("Regularizations"),
            "icon": "fas fa-check-circle",
            "link": reverse("regularization"),
        },
    ]

    return {
        "items": [
            {
                "count": counts.get(item["key"], 0),
                "title": item["title"],
                "icon": item["icon"],
                "link": request.build_absolute_uri(item["link"]),
            }
            for item in items
        ],
        "request": request,
    }

@register.simple_tag
def get_item(attendance_data, employee_id, date):
    """
    Get the attendance details (status and color) for a specific day from the provided attendance data,
    considering the statuses of the previous and next days.
    
    Logic:
    - If current status is "OFF" or "FL" and it falls between:
      - A and A (Absent-OFF-Absent) -> Mark as A
      - A and P (Absent-OFF-Present) -> Mark as A  
      - P and A (Present-OFF-Absent) -> Mark as A
    - Otherwise return the original status
    
    Args:
        attendance_data (dict): Dictionary containing attendance data
        employee_id: ID of the employee
        date: Date object for the current day
        
    Returns:
        list: List containing status and color information
    """
    
    def safe_get_status(entries, default_status="A", default_color="#FF0000"):
        """
        Safely extract status from attendance entries with proper fallback.
        
        Args:
            entries: Attendance entries (could be list, dict, or None)
            default_status: Default status if none found
            default_color: Default color if none found
            
        Returns:
            tuple: (status, color, full_entry)
        """
        if not entries:
            return default_status, default_color, {"status": default_status, "color": default_color}
        
        # Handle different data structures
        if isinstance(entries, list):
            if entries:
                # Get the last entry (most recent for the day)
                entry = entries[-1]
                if isinstance(entry, dict):
                    status = entry.get("status", default_status)
                    color = entry.get("color", default_color)
                    return status, color, entry
        elif isinstance(entries, dict):
            # If entries is a single dict
            status = entries.get("status", default_status)
            color = entries.get("color", default_color)
            return status, color, entries
        
        # Fallback
        return default_status, default_color, {"status": default_status, "color": default_color}
    
    try:
        # Safely get employee attendance data
        employee_attendance = attendance_data.get(employee_id, {}) if attendance_data else {}
        
        # Calculate dates
        current_date = date.date() if hasattr(date, 'date') else date
        prev_date = current_date - timedelta(days=1)
        next_date = current_date + timedelta(days=1)
        
        # Get attendance entries for all three days
        current_entries = employee_attendance.get(current_date, [])
        prev_entries = employee_attendance.get(prev_date, [])
        next_entries = employee_attendance.get(next_date, [])
        
        # Extract statuses safely
        current_status, current_color, current_entry = safe_get_status(current_entries)
        prev_status, _, _ = safe_get_status(prev_entries)
        next_status, _, _ = safe_get_status(next_entries)
        
        # Enhanced logic: Check if current status should be converted to "A"
        should_convert_to_absent = (
            current_status in ["OFF", "FL"] and
            (
                # Case 1: A-OFF-A (Absent-OFF-Absent)
                (prev_status == "A" and next_status == "A") or
                
                # Case 2: A-OFF-P (Absent-OFF-Present) 
                (prev_status == "A" and next_status == "P") or
                
                # Case 3: P-OFF-A (Present-OFF-Absent)
                (prev_status == "P" and next_status == "A")
                
                # Add more patterns as needed:
                # (prev_status == "P" and next_status == "P")  # P-OFF-P -> A
            )
        )
        
        if should_convert_to_absent:
            # Convert to Absent status
            return [{"status": "A", "color": "#FF0000"}]
        else:
            # Return original entries or default
            if current_entries:
                # Ensure we return a list format
                if isinstance(current_entries, list):
                    return current_entries
                else:
                    return [current_entries]
            else:
                # Default to Absent if no entries found
                return [{"status": "A", "color": "#FF0000"}]
                
    except (AttributeError, TypeError, KeyError) as e:
        # Log the error if you have logging configured
        # logger.error(f"Error in get_item template tag: {e}")
        
        # Return safe fallback
        return [{"status": "A", "color": "#FF0000"}]


@register.simple_tag  
def get_item_with_context(attendance_data, employee_id, date, conversion_rules=None):
    """
    Extended version with configurable conversion rules.
    
    Args:
        attendance_data (dict): Dictionary containing attendance data
        employee_id: ID of the employee  
        date: Date object for the current day
        conversion_rules (dict): Custom rules for status conversion
        
    Example conversion_rules:
    {
        "OFF": {
            ("A", "A"): "A",  # A-OFF-A -> A
            ("A", "P"): "A",  # A-OFF-P -> A  
            ("P", "A"): "A",  # P-OFF-A -> A
            ("P", "P"): "P",  # P-OFF-P -> P
        },
        "FL": {
            ("A", "A"): "A",  # A-FL-A -> A
            ("A", "P"): "A",  # A-FL-P -> A
        }
    }
    """
    
    # Default conversion rules
    default_rules = {
        "OFF": {
            ("A", "A"): "A",  # Absent-OFF-Absent -> Absent
            ("A", "P"): "A",  # Absent-OFF-Present -> Absent  
            ("P", "A"): "A",  # Present-OFF-Absent -> Absent
        },
        "FL": {
            ("A", "A"): "A",  # Absent-FL-Absent -> Absent
            ("A", "P"): "A",  # Absent-FL-Present -> Absent
            ("P", "A"): "A",  # Present-FL-Absent -> Absent
        }
    }
    
    # Use provided rules or defaults
    rules = conversion_rules or default_rules
    
    def safe_get_status(entries, default_status="A"):
        if not entries:
            return default_status
        if isinstance(entries, list) and entries:
            return entries[-1].get("status", default_status) if isinstance(entries[-1], dict) else default_status
        elif isinstance(entries, dict):
            return entries.get("status", default_status)
        return default_status
    
    try:
        employee_attendance = attendance_data.get(employee_id, {}) if attendance_data else {}
        
        current_date = date.date() if hasattr(date, 'date') else date
        prev_date = current_date - timedelta(days=1)
        next_date = current_date + timedelta(days=1)
        
        current_entries = employee_attendance.get(current_date, [])
        prev_entries = employee_attendance.get(prev_date, []) 
        next_entries = employee_attendance.get(next_date, [])
        
        current_status = safe_get_status(current_entries)
        prev_status = safe_get_status(prev_entries)
        next_status = safe_get_status(next_entries)
        
        # Check if current status has conversion rules
        if current_status in rules:
            status_rules = rules[current_status]
            pattern = (prev_status, next_status)
            
            if pattern in status_rules:
                new_status = status_rules[pattern]
                color = "#FF0000" if new_status == "A" else "#00FF00"
                return [{"status": new_status, "color": color}]
        
        # Return original or default
        return current_entries if current_entries else [{"status": "A", "color": "#FF0000"}]
        
    except Exception as e:
        return [{"status": "A", "color": "#FF0000"}]
    
@register.filter
def add_opacity(hex_color, opacity=0.5):
    """
    Convert a HEX color to RGBA with the given opacity.
    """
    try:
        hex_color = hex_color.lstrip("#")
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})"
    except Exception:
        # Fallback to transparent if invalid color
        return f"rgba(0, 0, 0, {opacity})"


@register.filter
def is_active(request_path, urls):
    """
    Checks if the current path matches any URL in a list.
    :param request_path: The current request path.
    :param urls: A comma-separated string of URLs.
    :return: True if the path matches one of the URLs, otherwise False.
    """
    url_list = urls.split(",")
    return request_path.strip() in url_list


@register.filter
def in_list(value, arg):
    return value in arg.split(",")


@register.inclusion_tag("hrms_app/charts/top_5_employees_duration_chart.html")
def render_top_5_employees_by_duration():
    return {"top_performer": "Top Performer"}


@register.inclusion_tag("includes/sync_attendance.html")
def load_attendance_form(form):
    return {"form": form}


@register.simple_tag
def get_employee_highlights():
    """
    This tag retrieves employees who have a birthday, marriage anniversary,
    or job anniversary today, along with random background colors for the carousel.
    """
    # Get employee highlights using the existing method
    today = now().date()
    employees = PersonalDetails.objects.filter(
        models.Q(birthday__month=today.month, birthday__day=today.day)
        | models.Q(marriage_ann__month=today.month, marriage_ann__day=today.day)
        | models.Q(doj__month=today.month, doj__day=today.day)
    )

    light_colors = [
        "bg-light-blue",
        "bg-light-pink",
        "bg-light-yellow",
        "bg-light-green",
        "bg-light-coral",
        "bg-light-cyan",
        "bg-light-lavender",
    ]

    for employee in employees:
        events = []
        if (
            employee.birthday
            and employee.birthday.month == today.month
            and employee.birthday.day == today.day
        ):
            events.append("🎉 Happy Birthday! 🎉")
        if (
            employee.marriage_ann
            and employee.marriage_ann.month == today.month
            and employee.marriage_ann.day == today.day
        ):
            events.append("💍 Happy Marriage Anniversary! 💍")
        if (
            employee.doj
            and employee.doj.month == today.month
            and employee.doj.day == today.day
        ):
            events.append("🎊 Happy Job Anniversary! 🎊")
        employee.events = events

        # Assign a random light color to each employee
        employee.bg_color = random.choice(light_colors)

    return employees


@register.filter
def add_days(date, days):
    return date + timedelta(days=days)


@register.filter
def localtime_filter(value):
    from django.utils.timezone import localtime

    return localtime(value)


@register.filter
def str_to_date(value):
    from django.utils.timezone import localtime, make_aware, utc

    date_time = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    # Convert to aware datetime objects if naive
    date_time = (
        make_aware(date_time, timezone=utc) if date_time.tzinfo is None else date_time
    )
    return date_time


@register.inclusion_tag(filename="leave_balances/holidays.html")
def get_holidays():
    return {"holidays": Holiday.objects.filter(year=now().year).order_by("start_date")}


@register.inclusion_tag(filename="leave_balances/announcement.html")
def get_announcement(user, request):
    announcements = (
        HRAnnouncement.objects.filter(is_active=True)
        .filter(start_date__lte=now().date())
        .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=now().date()))
        .order_by("-pinned", "-start_date")
    )

    return {"announcements": announcements, "user": user, "request": request}


@register.filter
def widget_type(field):
    """Returns the widget type as lowercase (e.g. 'textinput', 'radioselect')."""
    return field.field.widget.__class__.__name__.lower()
