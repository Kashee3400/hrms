from datetime import date, timedelta
from unittest import mock

from django.conf import settings

from hrms_app.models import AppSetting, AttendanceGap, AttendanceLog, Holiday, Notification
from hrms_app.services import attendance_gaps as engine
from hrms_app.services.notification_push import app_route
from hrms_app.tests.base import MobileTestCase, at


def codes(absent):
    def fake(user, start, end, today):
        return {
            start + timedelta(n): ("A" if start + timedelta(n) in absent else "P", None)
            for n in range((end - start).days + 1)
        }

    return fake


NOV = lambda day: date(2026, 11, day)  # Mon 2 ... Sun 8, Mon 9


class LastApplyDateTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        AppSetting.objects.create(key=engine.LIMIT_KEY, value="4")

    def test_three_working_days_after(self):
        self.assertEqual(engine.last_apply_date(NOV(3)), NOV(6))

    def test_sunday_is_skipped(self):
        self.assertEqual(engine.last_apply_date(NOV(5)), NOV(9))

    def test_holiday_is_skipped(self):
        Holiday.objects.create(title="H", start_date=NOV(6), end_date=NOV(6))
        self.assertEqual(engine.last_apply_date(NOV(3)), NOV(7))


class ScanTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.mail = mock.Mock()
        for patcher in (
            mock.patch.object(engine, "send_leave_application_email", self.mail),
            mock.patch.object(engine.transaction, "on_commit", lambda fn: fn()),
            mock.patch.object(engine, "day_codes", codes({NOV(4), NOV(5)})),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        AppSetting.objects.create(key=engine.LIMIT_KEY, value="4")
        self.boss = self.person(1, official_email="m@k.co")
        self.emp = self.person(7, official_email="e@k.co", reports_to=self.boss)
        self.peer = self.person(8, official_email="p@k.co", reports_to=self.boss)
        for day in (2, 3, 4, 5):
            self.log(self.peer, NOV(day))
        self.log(self.emp, NOV(2))
        self.log(self.emp, NOV(3), reg=settings.MIS_PUNCHING)

    def log(self, user, day, reg=None):
        moment = at(day)
        AttendanceLog.objects.create(
            applied_by=user,
            start_date=moment,
            end_date=moment,
            title=f"{user.pk}{day}",
            slug=f"{user.pk}-{day}",
            reg_status=reg,
            att_status="Present",
        )

    def switch(self, mode):
        AppSetting.objects.update_or_create(key=engine.MODE_KEY, defaults={"value": mode})
        AppSetting.objects.update_or_create(key=engine.START_KEY, defaults={"value": "2026-11-02"})

    def test_off_without_settings(self):
        self.assertEqual(engine.scan(NOV(6))["mode"], "off")

    def test_report_mode_only_tells_hr(self):
        self.switch("report")
        result = engine.scan(NOV(6))
        self.assertEqual((result["reminders"], Notification.objects.count()), (0, 0))
        self.assertEqual(self.mail.delay.call_args.args[0], "Attendance gap report")
        self.assertEqual(engine.open_groups(self.emp), [])

    def test_kinds(self):
        self.switch("report")
        engine.scan(NOV(6))
        self.assertEqual(
            {gap.date: gap.kind for gap in AttendanceGap.objects.filter(user=self.emp)},
            {NOV(3): "missing_punch", NOV(4): "no_record", NOV(5): "no_record"},
        )

    def test_excluded_codes_are_normalised_and_skipped(self):
        self.switch("report")
        AppSetting.objects.create(key=engine.EXCLUDE_KEY, value=" 8, kmpcl-099 ,")
        self.assertEqual(engine.excluded_codes(), {"KMPCL-008", "KMPCL-099"})
        engine.scan(NOV(6))
        self.assertFalse(AttendanceGap.objects.filter(user=self.peer).exists())

    def test_live_sends_one_digest_and_stays_quiet_on_a_rerun(self):
        self.switch("live")
        engine.scan(NOV(6))
        note = Notification.objects.get(receiver=self.emp)
        self.assertEqual(app_route(note), "/attendance/gaps")
        self.assertIn(["e@k.co"], [call.args[2] for call in self.mail.delay.call_args_list])
        engine.scan(NOV(6))
        self.assertEqual(Notification.objects.filter(receiver=self.emp).count(), 1)

    def test_groups_carry_their_deadline(self):
        self.switch("live")
        engine.scan(NOV(6))
        self.assertEqual(
            [(g.kind, g.start, g.end, g.deadline) for g in engine.open_groups(self.emp)],
            [("missing_punch", NOV(3), NOV(3), NOV(6)), ("no_record", NOV(4), NOV(5), NOV(9))],
        )

    def test_manager_hears_when_time_runs_out(self):
        self.switch("live")
        engine.scan(NOV(6))
        engine.scan(NOV(7))
        self.assertTrue(Notification.objects.filter(receiver=self.boss, message__contains="P7 Name").exists())

    def test_applied_leave_closes_the_days_at_once(self):
        self.switch("live")
        engine.scan(NOV(6))
        self.leave(self.emp, NOV(4), settings.PENDING, days=2)
        self.assertEqual([g.kind for g in engine.open_groups(self.emp)], ["missing_punch"])

    def test_health_alert_when_the_scan_never_ran(self):
        self.assertTrue(engine.check_health(NOV(6)))
        self.switch("live")
        self.assertFalse(engine.check_health(NOV(6)))
        engine._mark_run(NOV(6))
        self.assertTrue(engine.check_health(NOV(6)))

    def test_no_alert_before_there_is_anything_to_scan(self):
        self.switch("report")  # starts on 2 Nov
        self.assertTrue(engine.check_health(date(2026, 10, 31)))
        self.assertTrue(engine.check_health(NOV(2)))
        self.assertFalse(engine.check_health(NOV(3)))
