from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.conf import settings
from hrms_app.utility.leave_utils import get_employee_requested_leave,get_employee_requested_tour,get_regularization_requests
register = template.Library()

@register.simple_tag
def render_breadcrumb(title, urls):
    """
    Render breadcrumb HTML with dynamic title and URLs.
    
    :param title: Title for the breadcrumb section.
    :param urls: List of tuples containing URL name and URL kwargs.
    :return: Rendered breadcrumb HTML.
    """
    dashboard = reverse('dashboard')
    breadcrumb_html = f"""
    <div class="row border-bottom bd-lightGray m-3">
      <div class="cell-md-4 d-flex flex-align-center">
        <h3 class="dashboard-section-title text-center text-left-md w-90">{title}</h3>
      </div>

      <div class="cell-md-8 d-flex flex-justify-center flex-justify-end-md flex-align-center">
        <ul class="breadcrumbs bg-transparent">
        <li class="page-item"><a href="{dashboard}" class="page-link"><span class="mif-widgets"></span></a></li>
    """
    for url_name, url_kwargs in urls:
        url = reverse(url_name, kwargs={k: v for k, v in url_kwargs.items() if k != 'label'})
        breadcrumb_html += f'<li class="page-item"><a href="{url}" class="page-link">{url_kwargs.get("label")}</a></li>'

    breadcrumb_html += """
        </ul>
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
def load_pending_leaves(user):
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
