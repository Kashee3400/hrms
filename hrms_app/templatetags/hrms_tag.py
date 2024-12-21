from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.conf import settings
from hrms_app.utility.leave_utils import get_employee_requested_leave,get_employee_requested_tour,get_regularization_requests
register = template.Library()

@register.simple_tag
def render_breadcrumb(title, urls):
    """
    Render breadcrumb HTML with dynamic title and URLs using Bootstrap classes.

    :param title: Title for the breadcrumb section.
    :param urls: List of tuples containing URL name and URL kwargs.
    :return: Rendered breadcrumb HTML.
    """
    dashboard = reverse('dashboard')
    breadcrumb_html = f"""
    <div class="row border-bottom py-3 mb-3">
      <div class="col-md-4 d-flex align-items-center">
        <h3 class="dashboard-section-title text-center text-md-start w-100">{title}</h3>
      </div>

      <div class="col-md-8 d-flex justify-content-center justify-content-md-end align-items-center">
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb mb-0 bg-transparent">
            <li class="breadcrumb-item">
              <a href="{dashboard}">
                <i class="mdi mdi-home"></i>
              </a>
            </li>
    """
    for url_name, url_kwargs in urls:
        url = reverse(url_name, kwargs={k: v for k, v in url_kwargs.items() if k != 'label'})
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
    options = ''
    for choice in choices:
        selected = 'selected' if choice[0] == 'Pending' else ''
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
    if choice == '1':
        return 'Full Day'
    elif choice == '2':
        return 'First Half (Morning)'
    else:
        return 'Second Half (Afternoon)'
    

@register.inclusion_tag('notifications/leave_notification_list.html')
def load_notifications(user):
    pending_leaves = get_employee_requested_leave(user=user)
    pending_tours = get_employee_requested_tour(user=user)
    pending_reg = get_regularization_requests(user=user)
    total_counts = len(pending_leaves)+pending_tours.count()+pending_reg.count()
    return {'pending_leaves': pending_leaves,'pending_tours':pending_tours,'pending_reg':pending_reg,'count':total_counts}



@register.inclusion_tag('hrms_app/navigation/navigation.html', takes_context=True)
def render_employee_navigation(context):
    request = context['request']
    navigation_items = [
        {'name': 'Employees', 'url_name': 'employees', 'icon': 'mif-lock'},
        {'name': 'Register Employee', 'url_name': 'create_user', 'icon': 'mif-user-plus'},
        # Add more navigation items here
    ]
    
    for item in navigation_items:
        item['is_active'] = request.path == reverse(item['url_name'])
    
    return {
        'navigation_items': navigation_items,
        'is_parent_active': any(item['is_active'] for item in navigation_items)
    }

from hrms_app.models import AttendanceLog

@register.simple_tag
def get_attendance_for_day(employee, date, attendance_logs_cache=None):
    """
    Optimized template tag to fetch the attendance status for a given employee on a specific date.
    """
    # If the attendance_logs_cache is passed, use it to avoid multiple queries
    if attendance_logs_cache is None:
        attendance_logs_cache = {}

    # Check if the attendance log for the given employee and date exists in the cache
    cache_key = (employee.id, date.date())
    if cache_key in attendance_logs_cache:
        return attendance_logs_cache[cache_key]

    # Otherwise, query the database for the specific log with only the necessary field (att_status_short_code)
    attendance_log = AttendanceLog.objects.filter(
        applied_by=employee,
        start_date__date=date.date()
    ).values('att_status_short_code').first()

    # Cache the result
    if attendance_log:
        status = attendance_log['att_status_short_code']
    else:
        status = "NA"

    attendance_logs_cache[cache_key] = status
    return status

@register.simple_tag
def format_emp_code(emp_code):
    length = len(emp_code)
    if length == 1:
        return f"KMPCL-00{emp_code}"
    elif length == 2:
        return f"KMPCL-0{emp_code}"
    else:
        return f"KMPCL-{emp_code}"

@register.simple_tag
def get_item(attendance_data, employee_id, day):
    """
    Get the attendance details (status and color) for a specific day from the provided attendance data.
    """
    # Fetch the attendance entries for the employee on that day
    employee_attendance = attendance_data.get(employee_id, {})
    attendance_entries = employee_attendance.get(day, [])

    # If there are no entries, return a default value
    if not attendance_entries:
        return [{"status": "A", "color": "#FF0799"}]

    # Return the list of attendance entries (status and color)
    return attendance_entries

@register.filter
def add_opacity(hex_color, opacity=0.5):
    """
    Convert a HEX color to RGBA with the given opacity.
    """
    try:
        hex_color = hex_color.lstrip("#")
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
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
    url_list = urls.split(',')
    return request_path.strip() in url_list