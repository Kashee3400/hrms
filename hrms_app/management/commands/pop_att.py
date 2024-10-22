from django.utils.text import slugify
from hrms_app.models import AttendanceLog, CustomUser
from hrms_app.hrms.utils import call_soap_api 
from hrms_app.models import AttendanceSetting, EmployeeShift,AttendanceStatusColor,DeviceInformation
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from django.core.management.base import BaseCommand
import pytz
from django.conf import settings


class Command(BaseCommand):
    help = 'Populate AttendanceLog data from API and Holidays'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help="Populate attendance for a specific user ID")
        parser.add_argument('--from-date', type=str, help="Start date for the attendance log")
        parser.add_argument('--to-date', type=str, help="End date for the attendance log")

    def handle(self, *args, **options):
        self.stdout.write('Starting to populate AttendanceLog data...')

        # Step 1: Fetch static data outside the loop
        half_day_color = AttendanceStatusColor.objects.get(status=settings.HALF_DAY)
        present_color = AttendanceStatusColor.objects.get(status=settings.PRESENT)
        absent_color = AttendanceStatusColor.objects.get(status=settings.ABSENT)
        asettings = AttendanceSetting.objects.first()
        if options['user_id']:
            users = CustomUser.objects.filter(id=options['user_id']).select_related('personal_detail')
        else:
            users = CustomUser.objects.all().select_related('personal_detail')

        device_instance = DeviceInformation.objects.all().first()
        result = call_soap_api(device_instance=device_instance)

        # Step 4: Prepare to bulk insert attendance logs
        attendance_logs_to_create = []
        kolkata_tz = pytz.timezone('Asia/Kolkata')

        # Step 5: Iterate over users and match them with API result efficiently
        for user in users:
            emp_code = user.personal_detail.employee_code

            # Skip users without a matching employee code in the result
            if emp_code not in result:
                continue

            emp_shift = EmployeeShift.objects.filter(employee=user).select_related('shift_timing').first()
            user_shift = emp_shift.shift_timing if emp_shift else None

            # If no shift is found, skip this user
            if not user_shift:
                self.stdout.write(f'No shift found for user: {user.get_full_name()}')
                continue

            # Process attendance logs for this user
            for date, log_times in result[emp_code].items():
                login_date_time, logout_date_time = log_times[0], log_times[-1]
                total_duration = logout_date_time - login_date_time
                duration = (datetime.min + total_duration).time()

                # Calculate expected logout time and duration
                full_day_hours = asettings.full_day_hours
                user_expected_logout_date_time = login_date_time + timedelta(hours=full_day_hours)
                user_expected_logout_time = user_expected_logout_date_time.time()

                # Determine attendance status
                att_status, color_hex_code, reg_status, is_regularization, rfrom_date, rto_date, reg_duration,status,att_status_short_code = self.determine_attendance_status(
                    login_date_time, logout_date_time, total_duration, user_shift, full_day_hours, 
                    half_day_color, present_color, absent_color, user_expected_logout_time, user_expected_logout_date_time
                )

                # Make dates timezone-aware
                rfrom_date_aware = kolkata_tz.localize(rfrom_date) if rfrom_date else None
                rto_date_aware = kolkata_tz.localize(rto_date) if rto_date else None

                # Create AttendanceLog instance but do not save yet
                attendance_logs_to_create.append(AttendanceLog(
                    applied_by=user,
                    title=f'Attendance for {user.get_full_name()} on {date}',
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
                    slug=slugify(f'{user.get_full_name()}-{date}'),
                    color_hex=color_hex_code
                ))

        # Step 6: Bulk create the attendance logs
        AttendanceLog.objects.bulk_create(attendance_logs_to_create)

        self.stdout.write('Completed populating AttendanceLog data.')

    def determine_attendance_status(self, login_date_time, logout_date_time, total_duration, user_shift, 
                                    full_day_hours, half_day_color, present_color, absent_color, user_expected_logout_time, user_expected_logout_date_time):
        # (Same as before - no major changes here, only logic adjustments as needed)
        total_hours = total_duration.total_seconds() / 3600
        is_regularization = False
        reg_status = None
        status = None
        rfrom_date = rto_date = reg_duration = None
        color_hex_code = absent_color.color_hex
        att_status = settings.ABSENT
        att_status_short_code = 'A'
        if total_hours != 0:
            if login_date_time.time() <= user_shift.grace_start_time and total_hours >= full_day_hours and logout_date_time.time() >= user_shift.end_time:
                att_status = settings.PRESENT
                att_status_short_code = 'P'
                color_hex_code = present_color.color_hex
            elif self.is_late_coming(login_date_time, logout_date_time, user_shift):
                att_status = settings.HALF_DAY
                att_status_short_code = 'H'
                reg_status = settings.LATE_COMING
                status = settings.PENDING
                is_regularization = True
                str_from_date = f'{login_date_time.date()} {user_shift.grace_start_time}'
                rfrom_date = datetime.strptime(str_from_date, '%Y-%m-%d %H:%M:%S')
                rto_date = login_date_time
                rtotal_duration = rto_date - rfrom_date
                reg_duration = (datetime.min + rtotal_duration).time()
                color_hex_code = half_day_color.color_hex
            elif self.is_early_going(login_date_time, logout_date_time, user_shift, user_expected_logout_time):
                att_status = settings.HALF_DAY
                att_status_short_code = 'H'
                reg_status = settings.EARLY_GOING
                status = settings.PENDING
                is_regularization = True
                rfrom_date = logout_date_time
                if user_expected_logout_date_time.time() < user_shift.end_time:
                    str_to_date = f'{login_date_time.date()} {user_shift.end_time}'
                    user_expected_logout_date_time = datetime.strptime(str_to_date, '%Y-%m-%d %H:%M:%S')
                rto_date = user_expected_logout_date_time
                rtotal_duration = rto_date - rfrom_date
                reg_duration = (datetime.min + rtotal_duration).time()
                color_hex_code = half_day_color.color_hex
            elif login_date_time.time() >= user_shift.grace_start_time and logout_date_time.time() < user_shift.end_time:
                att_status = settings.HALF_DAY
                color_hex_code = half_day_color.color_hex
                rto_date = user_expected_logout_date_time
                att_status_short_code = 'H'
                

        else:
            att_status = settings.ABSENT
            reg_status = settings.MIS_PUNCHING
            status = settings.PENDING
            att_status_short_code = 'A'
            color_hex_code = absent_color.color_hex
            is_regularization = True
            rfrom_date = login_date_time
            rto_date = user_expected_logout_date_time

        return att_status, color_hex_code, reg_status, is_regularization, rfrom_date, rto_date, reg_duration,status,att_status_short_code

    def is_late_coming(self, login_date_time, logout_date_time, user_shift):
        return login_date_time.time() >= user_shift.grace_start_time and (logout_date_time.time() < user_shift.grace_end_time or logout_date_time.time() > user_shift.end_time)

    def is_early_going(self, login_date_time, logout_date_time, user_shift, user_expected_logout_time):
        return login_date_time.time() <= user_shift.grace_start_time and logout_date_time.time() < user_expected_logout_time
