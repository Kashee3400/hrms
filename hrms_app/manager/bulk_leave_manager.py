from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
from django.db import models
from ..models import LeaveApplication, LeaveDay

User = get_user_model()

# managers.py - Update with complete manager

class BulkLeaveApplicationManager(models.Manager):
    """Manager for handling bulk leave application creation."""
    
    def create_bulk_leave_applications(
        self,
        leave_type,
        start_date,
        end_date,
        employee_ids=None,
        select_all_employees=False,
        reason="",
        start_day_choice="full_day",
        end_day_choice="full_day",
        created_by=None,
    ):
        """
        Create leave applications for multiple employees.
        
        Returns:
            dict with 'success_count', 'failed_count', 'errors', 'applications', 'skipped'
        """
        
        # Validate dates
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date.")
        
        # Determine which employees to create leave for
        if select_all_employees:
            employees = User.objects.filter(is_active=True).exclude(is_staff=True)
        elif employee_ids:
            employees = User.objects.filter(id__in=employee_ids, is_active=True)
        else:
            raise ValueError("Either select employees or select all employees.")
        
        # Calculate used leave days
        used_leave = self._calculate_leave_days(
            start_date, 
            end_date, 
            start_day_choice, 
            end_day_choice
        )
        
        results = {
            'success_count': 0,
            'failed_count': 0,
            'errors': [],
            'applications': [],
            'skipped': []
        }
        
        # Create leave applications for each employee
        for employee in employees:
            try:
                # Check if employee already has leave in this date range
                if self._has_overlapping_leave(employee, start_date, end_date):
                    results['skipped'].append({
                        'employee_id': employee.id,
                        'employee_name': employee.get_full_name(),
                        'reason': 'Already has leave in this date range'
                    })
                    continue
                
                # # Calculate balance leave
                # balance_leave = self._calculate_balance_leave(
                #     employee, 
                #     leave_type, 
                #     used_leave
                # )

                # # Check if employee has sufficient leave balance
                # if balance_leave < 0:
                #     results['skipped'].append({
                #         'employee_id': employee.id,
                #         'employee_name': employee.get_full_name(),
                #         'reason': 'Insufficient leave balance'
                #     })
                #     continue
                
                # Create the leave application
                leave_app = LeaveApplication.objects.create(
                    appliedBy=employee,
                    leave_type=leave_type,
                    startDate=start_date,
                    endDate=end_date,
                    usedLeave=0,
                    balanceLeave=0,
                    reason=reason,
                    startDayChoice=start_day_choice,
                    endDayChoice=end_day_choice,
                    status='approved',
                )
                
                # Create corresponding leave days
                self._create_leave_days(leave_app, start_date, end_date)
                
                results['success_count'] += 1
                results['applications'].append({
                    'application_no': leave_app.applicationNo,
                    'employee_id': employee.id,
                    'employee_name': employee.get_full_name(),
                    'status': leave_app.status
                })
                
            except Exception as e:
                results['failed_count'] += 1
                results['errors'].append({
                    'employee_id': employee.id,
                    'employee_name': employee.get_full_name(),
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    def _calculate_leave_days(start_date, end_date, start_choice, end_choice):
        """Calculate number of leave days based on date range and half/full day choices."""
        delta = (end_date.date() - start_date.date()).days + 1
        
        if delta == 1:  # Single day leave
            if start_choice == "full_day":
                return 1.0
            else:  # Half day
                return 0.5
        else:  # Multiple days
            full_days = delta
            
            # Adjust for partial days
            if start_choice != "full_day":
                full_days -= 0.5
            
            if end_choice != "full_day":
                full_days -= 0.5
            
            return float(full_days)
    
    @staticmethod
    def _has_overlapping_leave(employee, start_date, end_date):
        """Check if employee already has approved/pending leave in date range."""
        overlapping = LeaveApplication.objects.filter(
            appliedBy=employee,
            startDate__lte=end_date,
            endDate__gte=start_date,
            status__in=['approved', 'pending']
        ).exists()
        return overlapping
    
    @staticmethod
    def _calculate_balance_leave(employee, leave_type, used_leave):
        """Calculate remaining leave balance for employee."""
        try:
            # Get employee's total leave allocation for this leave type
            total_allocation = leave_type.allowed_days_per_year or 0
            
            # Get used leave in current year
            current_year = datetime.now().year
            used_leaves = LeaveApplication.objects.filter(
                appliedBy=employee,
                leave_type=leave_type,
                status='approved',
                applyingDate__year=current_year
            ).aggregate(total=models.Sum('usedLeave'))['total'] or 0
            
            available_balance = total_allocation - used_leaves
            return available_balance - used_leave
        except Exception:
            # Fallback calculation
            allocation = leave_type.default_allocation or 0
            return allocation - used_leave
    
    @staticmethod
    def _create_leave_days(leave_application, start_date, end_date):
        """Create individual LeaveDay records for the leave period."""
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            LeaveDay.objects.get_or_create(
                leave_application=leave_application,
                date=current_date,
                defaults={'is_full_day': True}
            )
            current_date += timedelta(days=1)

