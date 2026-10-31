from datetime import date, timedelta
from unittest import mock

from django.conf import settings

from hrms_app.models import AppSetting, LeaveApplication, Notification, UserTour
from hrms_app.services import approval_reminders as reminders
from hrms_app.services.mobile import notifications as feed
from hrms_app.services.notification_push import app_route
from hrms_app.tests.base import MobileTestCase, at

MONDAY = date(2030, 1, 7)


class ReminderTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        for patcher in (
            mock.patch.object(reminders, "_is_working_day", lambda day: day.weekday() < 6),
            mock.patch("hrms_app.services.attendance_gaps._queue_mail"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.boss = self.person(1)
        self.admin = self.person(2, designation=self.admin_designation)
        self.a = self.person(3, reports_to=self.boss)
        self.b = self.person(4, reports_to=self.boss)
        self.c = self.person(5, reports_to=self.boss)

        day = MONDAY + timedelta(7)
        self.leave(self.a, day, settings.PENDING)
        self.tour(self.b, day, day, settings.PENDING)
        self.leave(self.a, day + timedelta(1), settings.RECOMMEND, kind=self.lwp)
        fresh = self.leave(self.c, day + timedelta(2), settings.PENDING)

        waited = at(MONDAY - timedelta(7))
        LeaveApplication.objects.exclude(pk=fresh.pk).update(updatedAt=waited)
        UserTour.objects.update(updated_at=waited)
        LeaveApplication.objects.filter(pk=fresh.pk).update(updatedAt=at(MONDAY))

    def switch_on(self):
        AppSetting.objects.create(key=reminders.REMINDER_DAYS_KEY, value="2")

    def test_off_until_set(self):
        self.assertEqual(reminders.send_approval_reminders(MONDAY), 0)

    def test_sunday_is_skipped(self):
        self.switch_on()
        self.assertEqual(reminders.send_approval_reminders(MONDAY - timedelta(1)), 0)

    def test_each_reviewer_hears_what_waited(self):
        self.switch_on()
        self.assertEqual(reminders.send_approval_reminders(MONDAY), 2)
        note = Notification.objects.get(receiver=self.boss)
        self.assertTrue(note.message.startswith("1 leave request and 1 tour request"))  # not the fresh one
        self.assertEqual(app_route(note), "/approvals")
        self.assertTrue(Notification.objects.get(receiver=self.admin).message.startswith("1 leave request "))

    def test_second_run_the_same_day_is_silent(self):
        self.switch_on()
        reminders.send_approval_reminders(MONDAY)
        Notification.objects.update(timestamp=at(MONDAY))
        self.assertEqual(reminders.send_approval_reminders(MONDAY), 0)
        self.assertEqual(Notification.objects.filter(receiver=self.boss).count(), 1)

    def test_tapping_it_in_the_feed_opens_the_queue(self):
        self.switch_on()
        reminders.send_approval_reminders(MONDAY)
        item = feed.get_feed(self.boss, filter_by=None, page=1)["results"][0]
        self.assertEqual((item["route"], item["title"]), ("/approvals", "Waiting for Your Decision"))

    def test_tours_alone_open_the_tours_tab(self):
        self.switch_on()
        LeaveApplication.objects.all().delete()
        reminders.send_approval_reminders(MONDAY)
        self.assertEqual(app_route(Notification.objects.get(receiver=self.boss)), "/approvals?tab=tours")

    def test_locked_requests_drop_out(self):
        self.switch_on()
        LeaveApplication.objects.all().delete()
        with mock.patch("hrms_app.services.mobile.team_tours.tour_lock", return_value={"is_locked": True}):
            self.assertEqual(reminders.send_approval_reminders(MONDAY), 0)

    def test_working_days_are_what_count(self):
        self.assertTrue(reminders._has_waited(at(MONDAY), MONDAY + timedelta(2), 2))
        self.assertFalse(reminders._has_waited(at(MONDAY), MONDAY + timedelta(1), 2))
        self.assertFalse(reminders._has_waited(at(MONDAY + timedelta(5)), MONDAY + timedelta(7), 2))

    def test_bad_setting_means_off(self):
        AppSetting.objects.create(key=reminders.REMINDER_DAYS_KEY, value="x")
        self.assertEqual(reminders.reminder_days(), 0)
