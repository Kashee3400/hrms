from hrms_app.hrms.form import BulkAttendanceForm
from hrms_app.models import AttendanceLog
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction, models
from django.conf import settings
from django.views import View
from datetime import datetime
from django.utils.text import slugify
import json

User = get_user_model()


class BulkAttendanceView(LoginRequiredMixin, View):
    """
    Enhanced class-based view to handle bulk attendance marking using Django forms
    """
    template_name = 'hrms_app/employee/bulk_attendance.html'

    def get(self, request):
        form = BulkAttendanceForm()
        context = {
            'form': form,
            'employees': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
            'today': timezone.now().date(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = BulkAttendanceForm(request.POST)

        if form.is_valid():
            try:
                # Get cleaned data
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                start_time = form.cleaned_data['start_time']
                end_time = form.cleaned_data['end_time']
                title_prefix = form.cleaned_data['title_prefix']
                reason = form.cleaned_data['reason']

                # Create datetime objects
                start_datetime = timezone.make_aware(
                    datetime.combine(start_date, start_time)
                )
                end_datetime = timezone.make_aware(
                    datetime.combine(end_date, end_time)
                )

                # Get duration
                duration_time = form.get_duration_as_time()

                # Get selected employees
                employees = form.get_selected_employees()

                if not employees.exists():
                    messages.error(request, 'No valid employees selected.')
                    return render(request, self.template_name, {
                        'form': form,
                        'employees': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
                    })

                # Bulk create attendance logs
                created_count = 0
                skipped_count = 0

                with transaction.atomic():
                    for employee in employees:
                        # Generate unique title for each employee
                        title = f"{title_prefix} - {employee.get_full_name() or employee.username}"

                        # Check if attendance already exists
                        existing = AttendanceLog.objects.filter(
                            applied_by=employee,
                            start_date__date=start_datetime.date(),
                            end_date__date=end_datetime.date()
                        ).exists()

                        if not existing:
                            # Generate unique slug
                            base_slug = slugify(title)
                            slug = base_slug
                            counter = 1

                            while AttendanceLog.objects.filter(slug=slug).exists():
                                slug = f"{base_slug}-{counter}"
                                counter += 1

                            attendance_log = AttendanceLog.objects.create(
                                applied_by=employee,
                                start_date=start_datetime,
                                end_date=end_datetime,
                                title=title,
                                slug=slug,
                                duration=duration_time,
                                att_status=getattr(settings, 'ATTENDANCE_STATUS_PRESENT', 'present'),
                                att_status_short_code='P',
                                status=getattr(settings, 'APPROVED', 'approved'),
                                reason=reason,
                                is_submitted=True,
                                regularized_backend=True,
                                color_hex='#28a745',
                            )

                            # Add approval action
                            attendance_log.add_action(
                                action=getattr(settings, 'APPROVED', 'approved'),
                                performed_by=request.user,
                                comment=f"Bulk attendance marked by System"
                            )

                            created_count += 1
                        else:
                            skipped_count += 1

                # Show success message
                if created_count > 0:
                    duration_hours = form.get_duration().total_seconds() / 3600
                    success_msg = (
                        f'Successfully marked attendance as present for {created_count} employee(s) '
                        f'from {start_datetime.strftime("%Y-%m-%d %H:%M")} to {end_datetime.strftime("%Y-%m-%d %H:%M")} '
                        f'(Duration: {duration_hours:.1f} hours)'
                    )

                    if skipped_count > 0:
                        success_msg += f'. {skipped_count} records were skipped (already exist).'

                    messages.success(request, success_msg)
                else:
                    messages.warning(
                        request,
                        f'No new attendance records were created. All {skipped_count} records already exist for the selected date range.'
                    )

                return redirect('bulk_attendance')

            except Exception as e:
                messages.error(request, f'An error occurred while processing attendance: {str(e)}')
                return render(request, self.template_name, {
                    'form': form,
                    'employees': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
                })

        else:
            # Form has validation errors
            messages.error(request, 'Please correct the errors below.')
            return render(request, self.template_name, {
                'form': form,
                'employees': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
            })


class GetEmployeesAjaxView(LoginRequiredMixin, View):
    """
    Ajax endpoint to get employees data with additional details
    """

    def get(self, request):
        search_term = request.GET.get('search', '').strip()

        employees = User.objects.filter(is_active=True)

        if search_term:
            employees = employees.filter(
                models.Q(first_name__icontains=search_term) |
                models.Q(last_name__icontains=search_term) |
                models.Q(username__icontains=search_term) |
                models.Q(email__icontains=search_term)
            )

        employees = employees.values(
            'id', 'username', 'first_name', 'last_name', 'email'
        ).order_by('first_name', 'last_name')[:50]  # Limit to 50 results

        employees_data = []
        for emp in employees:
            full_name = f"{emp['first_name']} {emp['last_name']}".strip()
            if not full_name:
                full_name = emp['username']

            employees_data.append({
                'id': emp['id'],
                'name': full_name,
                'email': emp['email'],
                'username': emp['username']
            })

        return JsonResponse({
            'employees': employees_data,
            'total_active': User.objects.filter(is_active=True).count()
        })


class AttendancePreviewAjaxView(LoginRequiredMixin, View):
    """
    Ajax endpoint to preview attendance data with validation
    """

    def post(self, request):
        try:
            data = json.loads(request.body)

            # Create a form instance with the data
            form_data = {
                'start_date': data.get('start_date'),
                'end_date': data.get('end_date'),
                'start_time': data.get('start_time', '09:00'),
                'end_time': data.get('end_time', '18:00'),
                'select_all': data.get('select_all', False),
                'employees': data.get('employee_ids', [])
            }

            form = BulkAttendanceForm(form_data)

            if form.is_valid():
                # Get duration and employee information
                duration = form.get_duration()
                duration_hours = duration.total_seconds() / 3600
                employees = form.get_selected_employees()
                employee_count = employees.count()

                # Get sample employee names
                sample_employees = employees[:5]
                employee_names = [emp.get_full_name() or emp.username for emp in sample_employees]

                # Check for existing attendance records
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']

                existing_count = 0
                for emp in employees[:10]:  # Check first 10 employees for preview
                    if AttendanceLog.objects.filter(
                            applied_by=emp,
                            start_date__date=start_date,
                            end_date__date=end_date
                    ).exists():
                        existing_count += 1

                return JsonResponse({
                    'success': True,
                    'employee_count': employee_count,
                    'duration_hours': round(duration_hours, 2),
                    'sample_employees': employee_names,
                    'date_range': f"{start_date} to {end_date}",
                    'time_range': f"{form_data['start_time']} to {form_data['end_time']}",
                    'existing_records': existing_count,
                    'estimated_new_records': max(0, min(10, employee_count) - existing_count)
                })
            else:
                # Return validation errors
                errors = []
                for field, error_list in form.errors.items():
                    for error in error_list:
                        errors.append(f"{field}: {error}")

                return JsonResponse({
                    'success': False,
                    'errors': errors
                })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Preview failed: {str(e)}'
            })

    def get(self, request):
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method'
        })


class AttendanceStatsAjaxView(LoginRequiredMixin, View):
    """
    Ajax endpoint to get attendance statistics
    """

    def get(self, request):
        try:
            # Get date range from request
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            if not start_date or not end_date:
                return JsonResponse({'error': 'Date range required'}, status=400)

            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            # Get statistics
            total_logs = AttendanceLog.objects.filter(
                start_date__date__gte=start_date,
                end_date__date__lte=end_date
            ).count()

            present_logs = AttendanceLog.objects.filter(
                start_date__date__gte=start_date,
                end_date__date__lte=end_date,
                att_status=getattr(settings, 'ATTENDANCE_STATUS_PRESENT', 'present')
            ).count()

            backend_regularized = AttendanceLog.objects.filter(
                start_date__date__gte=start_date,
                end_date__date__lte=end_date,
                regularized_backend=True
            ).count()

            return JsonResponse({
                'total_logs': total_logs,
                'present_logs': present_logs,
                'backend_regularized': backend_regularized,
                'date_range': f"{start_date} to {end_date}"
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
