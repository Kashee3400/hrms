from datetime import date, time, timedelta
from types import SimpleNamespace

from django.conf import settings
from django.contrib import admin
from django.utils import timezone

from hrms_app.admin import AttendanceLogAdmin
from hrms_app.models import (
    AttendanceGap,
    AttendanceLog,
    AttendanceLogHistory,
    AttendanceSetting,
    AttendanceStatusColor,
    EmployeeShift,
    LeaveDay,
    LockStatus,
    Notification,
    ShiftTiming,
)
from hrms_app.services import attendance_marking as marking
from hrms_app.tests.base import MobileTestCase, at
from hrms_app.utility.report_utils import calculate_daily_tour_durations, generate_monthly_presence_data_detailed

DAY = date(2026, 10, 6)  # a Tuesday
TODAY = date(2026, 10, 13)
URL = "/api/v1/attendance/mark/"


def moment(hour, minute=0):
    return timezone.make_aware(timezone.datetime(DAY.year, DAY.month, DAY.day, hour, minute))


class MarkingCase(MobileTestCase):
    def setUp(self):
        super().setUp()
        shift = ShiftTiming.objects.create(
            start_time=time(9, 30),
            end_time=time(17, 30),
            grace_time=30,
            grace_start_time=time(10, 0),
            grace_end_time=time(18, 0),
            break_start_time=time(13, 30),
            break_end_time=time(14, 30),
            break_duration=60,
        )
        AttendanceSetting.objects.create(full_day_hours=8, half_day_hours=4)
        AttendanceStatusColor.objects.create(status=settings.PRESENT, color="green", color_hex="#06B900")
        AttendanceStatusColor.objects.create(status=settings.HALF_DAY, color="blue", color_hex="#0000FF")
        AttendanceStatusColor.objects.create(status=settings.ABSENT, color="red", color_hex="#FF0000")
        self.root = self.person(99, is_superuser=True)
        self.emp = self.person(7)
        EmployeeShift.objects.update_or_create(employee=self.emp, defaults={"shift_timing": shift})

    def log(self, start, end, code="H", reg=None):
        return AttendanceLog.objects.create(
            applied_by=self.emp,
            title="t",
            slug="t",
            start_date=start,
            end_date=end,
            duration=(timezone.datetime.min + (end - start)).time(),
            att_status=settings.HALF_DAY,
            att_status_short_code=code,
            reg_status=reg,
            is_regularisation=bool(reg),
        )

    def half_leave(self, half):
        leave = self.leave(self.emp, DAY, settings.APPROVED, days=1)
        leave.startDayChoice = half
        leave.endDayChoice = half
        type(leave).objects.filter(pk=leave.pk).update(startDayChoice=half, endDayChoice=half)
        LeaveDay.objects.create(leave_application=leave, date=DAY, is_full_day=False)

    def mark(self, kind, reason="Device was down", day=DAY):
        return marking.mark(self.root, self.emp, day, kind, reason, today=TODAY)

    def marked(self):
        return AttendanceLog.objects.get(applied_by=self.emp, start_date__date=DAY)

    def report(self):
        data = generate_monthly_presence_data_detailed(DAY, DAY, True, None, "")
        return data["7"][str(DAY)]["present"]


class FullDayTests(MarkingCase):
    def test_missing_punch_becomes_present(self):
        self.log(moment(9, 40), moment(9, 40), code="A", reg=settings.MIS_PUNCHING)
        self.assertIsNone(self.mark(marking.FULL_DAY))
        log = self.marked()
        self.assertEqual((log.att_status, log.att_status_short_code, log.color_hex), (settings.PRESENT, "P", "#06B900"))
        self.assertEqual(log.end_date, moment(17, 40))
        self.assertEqual(log.duration, time(8, 0))
        self.assertEqual(log.reg_status, None)
        self.assertTrue(log.regularized_backend and log.regularized and log.is_submitted)

    def test_late_coming_starts_at_grace(self):
        self.log(moment(11, 0), moment(18, 30), reg=settings.LATE_COMING)
        self.mark(marking.FULL_DAY)
        self.assertEqual(self.marked().start_date, moment(10, 0))
        self.assertEqual(self.marked().end_date, moment(18, 30))

    def test_history_says_who_and_keeps_the_original(self):
        self.log(moment(9, 40), moment(15, 0), reg=settings.EARLY_GOING)
        self.mark(marking.FULL_DAY)
        history = AttendanceLogHistory.objects.get()
        self.assertEqual(history.modified_by, self.root)
        self.assertEqual(history.previous_data["reg_status"], settings.EARLY_GOING)

    def test_employee_is_told(self):
        self.log(moment(9, 40), moment(15, 0))
        self.mark(marking.FULL_DAY)
        self.assertIn("Full Day Present", Notification.objects.get(receiver=self.emp).message)

    def test_open_gap_closes(self):
        self.log(moment(9, 40), moment(15, 0))
        AttendanceGap.objects.create(user=self.emp, date=DAY, kind=AttendanceGap.ABSENT)
        self.mark(marking.FULL_DAY)
        self.assertFalse(AttendanceGap.objects.get().is_open)


class HalfDayTests(MarkingCase):
    def test_second_half_is_filled_to_four_hours(self):
        self.half_leave(settings.FIRST_HALF)
        self.log(moment(14, 0), moment(17, 25))
        self.assertIsNone(self.mark(marking.SECOND_HALF))
        log = self.marked()
        self.assertEqual((log.att_status, log.att_status_short_code), (settings.HALF_DAY, "H"))
        self.assertEqual(log.end_date, moment(18, 0))
        self.assertEqual(log.duration, time(4, 0))

    def test_first_half_is_filled_to_four_hours(self):
        self.log(moment(9, 30), moment(13, 0))
        self.mark(marking.FIRST_HALF)
        self.assertEqual(self.marked().end_date, moment(13, 30))

    def test_a_longer_day_is_not_cut_short(self):
        self.log(moment(9, 30), moment(15, 0))
        self.mark(marking.FIRST_HALF)
        self.assertEqual(self.marked().end_date, moment(15, 0))

    def test_cannot_mark_the_half_the_leave_covers(self):
        self.half_leave(settings.FIRST_HALF)
        self.log(moment(9, 30), moment(13, 0))
        self.assertIn("first half", self.mark(marking.FIRST_HALF))

    def test_half_leave_rules_out_full_day(self):
        self.half_leave(settings.SECOND_HALF)
        self.log(moment(9, 30), moment(13, 0))
        self.assertIsNotNone(self.mark(marking.FULL_DAY))
        self.assertIsNone(self.mark(marking.FIRST_HALF))


class NoPunchTests(MarkingCase):
    def test_full_day_uses_the_shift(self):
        self.assertIsNone(self.mark(marking.FULL_DAY))
        log = self.marked()
        self.assertEqual((log.start_date, log.end_date), (moment(9, 30), moment(17, 30)))
        self.assertTrue(log.regularized_backend)

    def test_second_half_starts_at_lunch(self):
        self.mark(marking.SECOND_HALF)
        self.assertEqual((self.marked().start_date, self.marked().end_date), (moment(13, 30), moment(17, 30)))

    def test_report_shows_a_blank_times_and_r(self):
        self.mark(marking.FULL_DAY)
        row = self.report()
        self.assertEqual((row["status"], row["in_time"], row["out_time"], row["total_duration"], row["reg"]), ("A", "", "", "", "R"))

    def test_today_waits_for_the_sync(self):
        self.assertIn("No punch yet", marking.mark(self.root, self.emp, TODAY, marking.FULL_DAY, "x", today=TODAY))

    def test_undo_removes_the_row(self):
        self.mark(marking.FULL_DAY)
        AttendanceLogHistory.objects.get().revert()
        self.assertFalse(AttendanceLog.objects.filter(applied_by=self.emp).exists())


class ReportTests(MarkingCase):
    def test_keeps_the_real_punches_and_status(self):
        self.log(moment(14, 0), moment(17, 25), code="H", reg=settings.EARLY_GOING)
        self.mark(marking.SECOND_HALF)
        row = self.report()
        self.assertEqual((row["status"], row["in_time"], row["out_time"], row["reg"]), ("H", "02:00", "05:25", "R"))

    def test_mis_punch_shows_original_a(self):
        self.log(moment(9, 40), moment(9, 40), code="A", reg=settings.MIS_PUNCHING)
        self.mark(marking.FULL_DAY)
        row = self.report()
        self.assertEqual((row["status"], row["out_time"], row["reg"]), ("A", "", "R"))

    def test_second_mark_still_shows_the_first_original(self):
        self.log(moment(14, 0), moment(17, 25), code="H", reg=settings.EARLY_GOING)
        self.mark(marking.SECOND_HALF)
        self.mark(marking.FULL_DAY)
        self.assertEqual(self.report()["out_time"], "05:25")


class RefusalTests(MarkingCase):
    def test_future(self):
        self.assertIn("future", marking.mark(self.root, self.emp, TODAY + timedelta(1), marking.FULL_DAY, "x", today=TODAY))

    def test_before_joining(self):
        self.assertIn("before", self.mark(marking.FULL_DAY, day=date(2019, 1, 1)))

    def test_locked(self):
        LockStatus.objects.create(is_locked="locked", from_date=DAY, to_date=DAY, reason="Audit")
        self.assertIsNotNone(self.mark(marking.FULL_DAY))
        self.assertFalse(AttendanceLog.objects.exists())

    def test_reason_is_required(self):
        self.assertEqual(self.mark(marking.FULL_DAY, reason="  "), "Please give a reason.")

    def test_full_leave(self):
        leave = self.leave(self.emp, DAY, settings.APPROVED)
        LeaveDay.objects.create(leave_application=leave, date=DAY, is_full_day=True)
        self.assertIn("CL", self.mark(marking.FIRST_HALF))


class ApiTests(MarkingCase):
    def test_superuser_only(self):
        params = {"user_id": self.emp.pk, "date": str(DAY)}
        self.assertEqual(self.client_for(self.emp).get(URL, params).status_code, 403)
        boss = self.person(1, is_staff=True)
        self.assertEqual(self.client_for(boss).post(URL, params, format="json").status_code, 403)

    def test_get_then_post(self):
        client = self.client_for(self.root)
        self.log(moment(14, 0), moment(17, 25))
        params = {"user_id": self.emp.pk, "date": str(DAY)}
        data = client.get(URL, params).data["data"]
        self.assertEqual(data["punch"]["worked"], "03:25")
        self.assertEqual([o["kind"] for o in data["options"]], ["full", "first_half", "second_half"])
        res = client.post(URL, {**params, "kind": "second_half", "reason": "Half day"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["data"]["already_marked"])

    def test_bad_input(self):
        client = self.client_for(self.root)
        self.assertEqual(client.get(URL, {"user_id": self.emp.pk, "date": "x"}).status_code, 400)
        self.assertEqual(client.get(URL, {"user_id": "abc", "date": str(DAY)}).status_code, 400)


class AdminActionTests(MarkingCase):
    def run_action(self, log):
        request = SimpleNamespace(user=self.root)
        AttendanceLogAdmin(AttendanceLog, admin.site).approve_attendance(request, AttendanceLog.objects.filter(pk=log.pk))

    def test_history_names_the_admin(self):
        log = self.log(moment(9, 40), moment(9, 40), code="A", reg=settings.MIS_PUNCHING)
        self.run_action(log)
        self.assertEqual(AttendanceLogHistory.objects.get().modified_by, self.root)

    def test_late_coming_counts_from_the_corrected_start(self):
        log = self.log(moment(11, 0), moment(18, 30), reg=settings.LATE_COMING)
        AttendanceLog.objects.filter(pk=log.pk).update(from_date=moment(10, 0), to_date=moment(11, 0))
        self.run_action(log)
        log.refresh_from_db()
        self.assertEqual((log.att_status_short_code, log.regularized_backend), ("P", True))
        self.assertEqual(log.duration.hour, 8)


class TourDurationTests(MarkingCase):
    def test_uses_this_employees_log(self):
        other = self.person(8)
        AttendanceLog.objects.create(
            applied_by=other, title="o", slug="o", start_date=moment(9, 30), end_date=moment(17, 30),
            duration=time(8, 0), att_status=settings.PRESENT, att_status_short_code="P",
        )
        rows = calculate_daily_tour_durations(DAY, time(15, 0), DAY, time(17, 0), False, self.emp.pk)
        self.assertEqual(rows[0][1], "TH")  # two hours, the colleague's eight don't count
