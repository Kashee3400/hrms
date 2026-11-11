from datetime import date

from django.conf import settings

from hrms_app.models import LeaveApplication, LeaveType
from hrms_app.services.mobile.my_leaves import monthly_taken
from hrms_app.tests.base import MobileTestCase


class MonthlyTakenTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.emp = self.person(7)
        self.el = LeaveType.objects.create(leave_type="Earned", leave_type_short_code="EL", color_hex="#CA00BB")

    def month(self, data, number):
        return {item["code"]: item["days"] for item in data["months"][number - 1]["items"]}

    def test_counts_approved_days_by_month(self):
        self.leave(self.emp, date(2026, 1, 6), settings.APPROVED, days=2)  # Tue, Wed
        self.leave(self.emp, date(2026, 1, 13), settings.PENDING)
        self.leave(self.emp, date(2026, 1, 14), settings.REJECTED)
        data = monthly_taken(self.emp, 2026)
        self.assertEqual(self.month(data, 1), {"CL": 2})
        self.assertEqual(data["paid_days"], 2)

    def test_a_leave_across_months_is_split(self):
        self.leave(self.emp, date(2026, 1, 30), settings.APPROVED, kind=self.el, days=4)  # Fri..Mon
        data = monthly_taken(self.emp, 2026)
        self.assertEqual(self.month(data, 1), {"EL": 2})  # Fri, Sat
        self.assertEqual(self.month(data, 2), {"EL": 2})  # Sun counts for EL, Mon

    def test_half_day(self):
        leave = self.leave(self.emp, date(2026, 3, 3), settings.APPROVED)
        LeaveApplication.objects.filter(pk=leave.pk).update(startDayChoice=settings.FIRST_HALF, endDayChoice=settings.FIRST_HALF)
        self.assertEqual(self.month(monthly_taken(self.emp, 2026), 3), {"CL": 0.5})

    def test_lwp_is_unpaid_and_short_leave_left_out(self):
        self.leave(self.emp, date(2026, 4, 7), settings.APPROVED, kind=self.lwp)
        stl = LeaveType.objects.create(leave_type="Short", leave_type_short_code="STL", color_hex="#222222")
        self.leave(self.emp, date(2026, 4, 8), settings.APPROVED, kind=stl)
        data = monthly_taken(self.emp, 2026)
        self.assertEqual(self.month(data, 4), {"LWP": 1})
        self.assertEqual((data["paid_days"], data["unpaid_days"]), (0, 1))
        self.assertTrue(data["totals"][0]["is_unpaid"])

    def test_other_years_are_left_out(self):
        self.leave(self.emp, date(2025, 12, 30), settings.APPROVED, days=3)  # Tue..Thu
        data = monthly_taken(self.emp, 2026)
        self.assertEqual(self.month(data, 1), {"CL": 1})
        self.assertEqual(len(data["months"]), 12)

    def test_in_the_overview(self):
        self.leave(self.emp, date(2026, 1, 6), settings.APPROVED)
        data = self.client_for(self.emp).get("/api/v1/leave/overview/", {"year": 2026}).data["data"]
        self.assertEqual(data["monthly"]["paid_days"], 1)
