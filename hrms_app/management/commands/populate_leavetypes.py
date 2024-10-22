# your_app/management/commands/populate_leavetypes.py

from django.core.management.base import BaseCommand
from django.conf import settings
from hrms_app.models import LeaveType, CustomUser  # Adjust the import according to your app's structure

class Command(BaseCommand):
    help = 'Populate the LeaveType model based on settings.LEAVE_TYPE_CHOICES'

    def handle(self, *args, **options):
        for leave_type, leave_type_display in settings.LEAVE_TYPE_CHOICES:
            LeaveType.objects.get_or_create(
                leave_type=leave_type,
                defaults={
                    'leave_type_short_code': leave_type[:3].upper(),  # Example for short code
                    'min_notice_days': 0,
                    'max_days_limit': 0,
                    'min_days_limit': 0,
                    'allowed_days_per_year': 0,
                    'leave_fy_start': None,
                    'leave_fy_end': None,
                    'color_hex': '#5d298a',  # Default color
                }
            )
        self.stdout.write(self.style.SUCCESS('Successfully populated LeaveType model'))
