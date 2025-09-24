# management/commands/calculate_attendance_cache.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from datetime import timedelta, date
from ...services import AttendanceCacheService

class Command(BaseCommand):
    help = 'Calculate and cache attendance data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD). Defaults to yesterday.'
        )
        parser.add_argument(
            '--end-date', 
            type=str,
            help='End date (YYYY-MM-DD). Defaults to yesterday.'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=1,
            help='Number of days to process back from today (default: 1)'
        )
        parser.add_argument(
            '--employees',
            type=str,
            help='Comma-separated employee IDs to process (optional)'
        )
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='Force update existing cache entries'
        )
    
    def handle(self, *args, **options):
        try:
            # Parse dates
            if options['start_date'] and options['end_date']:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            else:
                end_date = date.today() - timedelta(days=1)  # Yesterday
                start_date = end_date - timedelta(days=options['days_back'] - 1)
            
            # Parse employee IDs
            employee_ids = None
            if options['employees']:
                employee_ids = [int(x.strip()) for x in options['employees'].split(',')]
            
            self.stdout.write(f"Processing attendance cache from {start_date} to {end_date}")
            
            # Calculate and store
            result = AttendanceCacheService.calculate_and_store_attendance(
                start_date=start_date,
                end_date=end_date,
                employee_ids=employee_ids,
                force_update=options['force_update']
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully processed attendance cache: "
                    f"{result['records_created']} created, {result['records_updated']} updated "
                    f"in {result['processing_time']:.2f} seconds"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to process attendance cache: {str(e)}")
            )
            raise
