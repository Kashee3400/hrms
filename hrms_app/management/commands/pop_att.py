from django.utils.text import slugify
from hrms_app.models import AttendanceLog,AttendanceStatusColor,AttendanceSetting,EmployeeShift
from hrms_app.hrms.managers import AttendanceStatusHandler
from hrms_app.hrms.utils import call_soap_api
from hrms_app.models import (
    DeviceInformation,
)
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from django.core.management.base import BaseCommand
import pytz
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class Command(BaseCommand):
    help = "Populate AttendanceLog data from API and Holidays"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", type=str, help="Populate attendance for a specific username"
        )
        parser.add_argument(
            "--from-date", type=str, help="Start date for the attendance log"
        )
        parser.add_argument(
            "--to-date", type=str, help="End date for the attendance log"
        )
    def fetch_static_data(self):
        half_day_color = AttendanceStatusColor.objects.get(status=settings.HALF_DAY)
        present_color = AttendanceStatusColor.objects.get(status=settings.PRESENT)
        absent_color = AttendanceStatusColor.objects.get(status=settings.ABSENT)
        asettings = AttendanceSetting.objects.first()
        return half_day_color, present_color, absent_color, asettings

    def get_users(self, username):
        if username:
            return User.objects.filter(username=username).select_related(
                "personal_detail"
            )
        return User.objects.all().select_related("personal_detail")

    def parse_dates(self, from_date_str, to_date_str):
        from_date = (
            make_aware(datetime.strptime(from_date_str, "%Y-%m-%d"))
            if from_date_str
            else None
        )
        to_date = (
            make_aware(datetime.strptime(to_date_str, "%Y-%m-%d"))
            if to_date_str
            else None
        )
        return from_date, to_date
    def get_user_shift(self, user):
        emp_shift = (
            EmployeeShift.objects.filter(employee=user)
            .select_related("shift_timing")
            .first()
        )
        return emp_shift.shift_timing if emp_shift else None

    def handle(self, *args, **options):
        self.stdout.write("Starting to populate AttendanceLog data...")

        # Fetch static data
        half_day_color, present_color, absent_color, asettings = self.fetch_static_data()
        users = self.get_users(options["username"])
        from_date, to_date = self.parse_dates(options["from_date"], options["to_date"])
        device_instance = DeviceInformation.objects.first()
        result = call_soap_api(device_instance=device_instance,from_date=from_date,to_date=to_date)
        # Prepare to bulk insert attendance logs
        attendance_logs_to_create = []
        kolkata_tz = pytz.timezone("Asia/Kolkata")

        # Iterate over users and match them with API result efficiently
        for user in users:
            emp_code = user.personal_detail.employee_code
            if emp_code not in result:
                continue
            user_shift = self.get_user_shift(user)
            if not user_shift:
                self.stdout.write(f"No shift found for user: {user.get_full_name()}")
                continue

            # Initialize the handler and creator objects
            status_handler = AttendanceStatusHandler(
                user_shift,
                asettings.full_day_hours,
                half_day_color,
                present_color,
                absent_color,
            )
            log_creator = AttendanceLogCreator(kolkata_tz)

            # Process the logs for the user
            attendance_logs_to_create.extend(
                self.process_user_attendance(
                    user, asettings, result[emp_code], log_creator, status_handler
                )
            )

        # Bulk create the attendance logs
        AttendanceLog.objects.bulk_create(attendance_logs_to_create)
        self.stdout.write("Completed populating AttendanceLog data.")

    def process_user_attendance(self, user, asettings, logs, log_creator, status_handler):
        attendance_logs = []
        full_day_hours = asettings.full_day_hours
        for date, log_times in logs.items():
            login_date_time, logout_date_time = log_times[0], log_times[-1]
            total_duration = logout_date_time - login_date_time
            duration = (datetime.min + total_duration).time()
            user_expected_logout_date_time = login_date_time + timedelta(hours=full_day_hours)
            user_expected_logout_time = user_expected_logout_date_time.time()

            status_data = status_handler.determine_attendance_status(
                login_date_time,
                logout_date_time,
                total_duration,
                user_expected_logout_time,
                user_expected_logout_date_time,
            )

            attendance_logs.append(
                log_creator.create_logs(
                    user, date, login_date_time, logout_date_time, duration, status_data
                )
            )
        return attendance_logs

class AttendanceLogCreator:
    def __init__(self, kolkata_tz):
        self.kolkata_tz = kolkata_tz

    def create_logs(self, user, date, login_date_time, logout_date_time, duration, status_data):
        att_status, color_hex_code, reg_status, is_regularization, rfrom_date, rto_date, reg_duration, status, att_status_short_code = status_data
        
        rfrom_date_aware = self.kolkata_tz.localize(rfrom_date) if rfrom_date else None
        rto_date_aware = self.kolkata_tz.localize(rto_date) if rto_date else None

        return AttendanceLog(
            applied_by=user,
            title=f"Attendance for {user.get_full_name()} on {date}",
            start_date=make_aware(login_date_time),
            end_date=make_aware(logout_date_time),
            duration=duration,
            is_regularisation=is_regularization,
            reg_status=reg_status,
            att_status=att_status,
            att_status_short_code=att_status_short_code,
            from_date=rfrom_date_aware,
            to_date=rto_date_aware,
            reg_duration=str(reg_duration),
            status=status,
            slug=slugify(f"{user.get_full_name()}-{date}"),
            color_hex=color_hex_code,
        )
