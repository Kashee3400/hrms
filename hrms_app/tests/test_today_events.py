from datetime import date, time, timedelta

from django.conf import settings

from hrms_app.models import EmployeeShift, Holiday, LeaveApplication, LeaveType, ShiftTiming
from hrms_app.services.mobile import recent_activity
from hrms_app.services.mobile.today_events import get_today_events
from hrms_app.tests.base import MobileTestCase

TODAY = date(2026, 11, 10)  # a Tuesday


class TodayEventsTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.emp = self.person(7)
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
        EmployeeShift.objects.update_or_create(employee=self.emp, defaults={"shift_timing": shift})

    def events(self, day=TODAY):
        return get_today_events(self.emp, day)

    def half(self, choice, status=settings.APPROVED):
        leave = self.leave(self.emp, TODAY, status)
        LeaveApplication.objects.filter(pk=leave.pk).update(startDayChoice=choice, endDayChoice=choice)
        return leave

    def test_nothing_on_a_working_day(self):
        self.assertEqual(self.events(), {"events": [], "short_leave": None})

    def test_full_day_leave(self):
        leave = self.leave(self.emp, TODAY, settings.APPROVED)
        [event] = self.events()["events"]
        self.assertEqual((event["kind"], event["part"], event["id"], event["code"]), ("leave", "full", leave.pk, "CL"))
        self.assertEqual((event["from"], event["to"]), ("09:30", "17:30"))

    def test_second_half_leave_starts_at_lunch(self):
        self.half(settings.SECOND_HALF)
        [event] = self.events()["events"]
        self.assertEqual((event["part"], event["from"], event["to"]), ("second_half", "13:30", "17:30"))

    def test_first_half_leave(self):
        self.half(settings.FIRST_HALF)
        [event] = self.events()["events"]
        self.assertEqual((event["part"], event["from"], event["to"]), ("first_half", "09:30", "13:30"))

    def test_middle_of_a_long_leave_is_full_day(self):
        leave = self.leave(self.emp, TODAY - timedelta(days=1), settings.APPROVED, days=3)
        LeaveApplication.objects.filter(pk=leave.pk).update(startDayChoice=settings.SECOND_HALF)
        self.assertEqual(self.events()["events"][0]["part"], "full")

    def test_pending_and_rejected_are_left_out(self):
        self.leave(self.emp, TODAY, settings.PENDING)
        self.leave(self.emp, TODAY, settings.REJECTED)
        self.assertEqual(self.events()["events"], [])

    def test_short_leave_is_not_an_event(self):
        stl = LeaveType.objects.create(leave_type="Short", leave_type_short_code="STL", color_hex="#222222")
        leave = self.leave(self.emp, TODAY, settings.APPROVED, kind=stl)
        LeaveApplication.objects.filter(pk=leave.pk).update(from_time=time(15, 30), to_time=time(17, 30))
        data = self.events()
        self.assertEqual(data["events"], [])
        self.assertEqual(data["short_leave"], {"id": leave.pk, "from": "15:30", "to": "17:30", "duration": "02:00"})

    def test_tour_today(self):
        tour = self.tour(self.emp, TODAY, TODAY + timedelta(days=1), settings.APPROVED)
        [event] = self.events()["events"]
        self.assertEqual((event["kind"], event["id"], event["from"], event["to"]), ("tour", tour.pk, "09:00", "23:59"))
        self.assertEqual(event["title"], "A → B")

    def test_holiday_and_sunday(self):
        Holiday.objects.create(title="Bhai Dooj", start_date=TODAY, end_date=TODAY, short_code="FL", color_hex="#FFD700")
        [event] = self.events()["events"]
        self.assertEqual((event["kind"], event["title"]), ("holiday", "Bhai Dooj"))
        [sunday] = self.events(date(2026, 11, 15))["events"]
        self.assertEqual(sunday["kind"], "off")

    def test_present_first_half_and_leave_second_half_ordered(self):
        self.half(settings.SECOND_HALF)
        self.tour(self.emp, TODAY, TODAY, settings.APPROVED)
        kinds = [(e["kind"], e["from"]) for e in self.events()["events"]]
        self.assertEqual(kinds, [("tour", "09:00"), ("leave", "13:30")])

    def test_in_the_home_today_payload(self):
        self.leave(self.emp, TODAY, settings.APPROVED)
        from unittest import mock

        from hrms_app.services.mobile import today_attendance

        with mock.patch.object(today_attendance, "_punches_with_deadline", return_value=([], True)):
            data = self.client_for(self.emp).get("/api/v1/home/today/").data["data"]
        self.assertIn("events", data)
        self.assertIn("short_leave", data)


class ShortLeaveActivityTests(MobileTestCase):
    def test_recent_activity_shows_hours(self):
        emp = self.person(7)
        stl = LeaveType.objects.create(leave_type="Short", leave_type_short_code="STL", color_hex="#222222")
        leave = self.leave(emp, TODAY, settings.APPROVED, kind=stl)
        LeaveApplication.objects.filter(pk=leave.pk).update(from_time=time(15, 30), to_time=time(17, 30))
        leave.refresh_from_db()
        self.assertEqual(recent_activity._amount(leave), "02:00 hrs")
        self.assertEqual(recent_activity._amount(self.leave(emp, TODAY, settings.APPROVED)), "1 day")
