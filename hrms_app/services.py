# services.py - Attendance Cache Service
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from collections import defaultdict
import logging
from .models import AttendanceCacheLog,AttendanceCache,CustomUser,AttendanceLog
from hrms_app.utility import attendanceutils as at

logger = logging.getLogger(__name__)

class AttendanceCacheService:
    """
    Service to handle attendance cache operations
    """
    
    @staticmethod
    def calculate_and_store_attendance(start_date, end_date, employee_ids=None, force_update=False):
        """
        Calculate and store attendance data in cache
        
        Args:
            start_date: Start date for calculation
            end_date: End date for calculation
            employee_ids: List of employee IDs (if None, process all)
            force_update: Whether to update existing cache entries
        """
        log_entry = AttendanceCacheLog.objects.create(
            process_type='daily',
            start_date=start_date,
            end_date=end_date,
            status='processing'
        )
        
        try:
            start_time = timezone.now()
            
            # Get employees to process
            if employee_ids:
                employees = CustomUser.objects.filter(id__in=employee_ids)
            else:
                employees = CustomUser.objects.filter(is_active=True)
            
            # Get all required data
            attendance_logs = AttendanceLog.objects.filter(
                start_date__date__range=[start_date, end_date]
            ).select_related('applied_by')
            
            leave_logs = at.get_leave_logs(employee_ids)
            tour_logs = at.get_tour_logs(employee_ids)
            holidays = at.get_holiday_logs()

            # Calculate attendance data using existing function
            attendance_data = at.map_attendance_data(
                attendance_logs, leave_logs, holidays, tour_logs, 
                start_date, end_date
            )
            
            records_created = 0
            records_updated = 0
            
            # Store in cache
            with transaction.atomic():
                for employee_id, employee_data in attendance_data.items():
                    for date_obj, status_data in employee_data.items():
                        if isinstance(date_obj, str):
                            date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
                        
                        if status_data:
                            primary_status = status_data[0]
                            
                            cache_obj, created = AttendanceCache.objects.update_or_create(
                                employee_id=employee_id,
                                date=date_obj,
                                defaults={
                                    'status': primary_status.get('status', 'A'),
                                    'color_hex': primary_status.get('color', '#000000'),
                                    'metadata': {
                                        'all_statuses': status_data,
                                        'calculated_at': timezone.now().isoformat()
                                    }
                                }
                            )
                            
                            if created:
                                records_created += 1
                            else:
                                records_updated += 1
            
            # Update log
            end_time = timezone.now()
            processing_time = (end_time - start_time).total_seconds()
            
            log_entry.status = 'completed'
            log_entry.employees_processed = employees.count()
            log_entry.records_created = records_created
            log_entry.records_updated = records_updated
            log_entry.processing_time_seconds = processing_time
            log_entry.completed_at = end_time
            log_entry.save()
            
            logger.info(f"Attendance cache updated: {records_created} created, {records_updated} updated")
            
            return {
                'success': True,
                'records_created': records_created,
                'records_updated': records_updated,
                'processing_time': processing_time
            }
            
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = timezone.now()
            log_entry.save()
            
            logger.error(f"Attendance cache calculation failed: {str(e)}")
            raise
    
    @staticmethod
    def get_cached_attendance(employee_ids, start_date, end_date):
        """
        Retrieve cached attendance data
        """
        cache_entries = AttendanceCache.objects.filter(
            employee_id__in=employee_ids,
            date__range=[start_date, end_date]
        ).select_related('employee')
        
        # Organize data similar to original function
        attendance_data = defaultdict(lambda: defaultdict(list))
        
        for entry in cache_entries:
            employee_id = entry.employee.id
            attendance_data[employee_id][entry.date] = [{
                'status': entry.status,
                'color': entry.color_hex
            }]
        
        return attendance_data
    
    @staticmethod
    def invalidate_cache(employee_ids=None, start_date=None, end_date=None):
        """
        Invalidate cache entries for specific criteria
        """
        queryset = AttendanceCache.objects.all()
        
        if employee_ids:
            queryset = queryset.filter(employee_id__in=employee_ids)
        
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        deleted_count = queryset.count()
        queryset.delete()
        
        logger.info(f"Invalidated {deleted_count} cache entries")
        return deleted_count


