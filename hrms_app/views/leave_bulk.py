# views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
from ..models import LeaveApplication, LeaveType
from django.views import View
from django.views.generic import FormView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import render
from datetime import datetime

from ..manager.bulk_leave_manager import BulkLeaveApplicationManager

User = get_user_model()


class BulkLeaveCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    login_url = 'login'
    permission_required = 'leave.add_leaveapplication'

    def get(self, request):
        context = {
            'leave_types': LeaveType.objects.all(),
            'employees': User.objects.filter(is_active=True).exclude(is_staff=True),
        }
        print(context)
        return render(request, 'hrms_app/employee/bulk_leave_create.html', context)

    def post(self, request):
        try:
            leave_type_id = request.POST.get('leave_type_id')
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            select_all_employees = request.POST.get('select_all_employees') == 'on'
            employee_ids = request.POST.getlist('employee_ids')
            reason = request.POST.get('reason', '')
            start_day_choice = request.POST.get('start_day_choice', 'full_day')
            end_day_choice = request.POST.get('end_day_choice', 'full_day')

            # Validation
            if not leave_type_id:
                return JsonResponse({'success': False, 'message': 'Leave type is required'})

            try:
                leave_type = LeaveType.objects.get(id=leave_type_id)
            except LeaveType.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Invalid leave type selected'})

            # Parse dates
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                start_date = datetime.combine(start_date.date(), datetime.min.time())
                end_date = datetime.combine(end_date.date(), datetime.max.time())
            except ValueError:
                return JsonResponse({'success': False, 'message': 'Invalid date format'})

            if start_date > end_date:
                return JsonResponse({'success': False, 'message': 'Start date cannot be after end date'})

            # Convert employee IDs
            if employee_ids:
                try:
                    employee_ids = [int(i) for i in employee_ids]
                except ValueError:
                    return JsonResponse({'success': False, 'message': 'Invalid employee selection'})

            if not select_all_employees and not employee_ids:
                return JsonResponse({
                    'success': False,
                    'message': 'Please select at least one employee or select all'
                })

            manager = BulkLeaveApplicationManager()
            result = manager.create_bulk_leave_applications(
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                employee_ids=employee_ids if not select_all_employees else None,
                select_all_employees=select_all_employees,
                reason=reason,
                start_day_choice=start_day_choice,
                end_day_choice=end_day_choice,
                created_by=request.user,
            )

            messages.success(
                request,
                f"Successfully created {result['success_count']} leave applications"
            )

            return JsonResponse({
                'success': True,
                'message': 'Bulk leave applications created successfully',
                'result': result
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=400)


class BulkLeaveHistoryView(LoginRequiredMixin, ListView):
    login_url = 'login'
    template_name = 'leave/bulk_leave_history.html'
    context_object_name = 'leave_applications'

    def get_queryset(self):
        return LeaveApplication.objects.filter(
            status='approved'
        ).select_related(
            'appliedBy', 'leave_type'
        ).order_by('-applyingDate')
