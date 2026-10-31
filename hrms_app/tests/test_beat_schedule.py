import re
from datetime import date
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import timezone

from hrms import celery_app
from hrms_app import tasks
from hrms_app.models import LeaveBalanceOpenings, LeaveType
from hrms_app.tests.base import MobileTestCase


class BeatScheduleTests(SimpleTestCase):
    def test_every_scheduled_task_exists(self):
        source = (Path(settings.BASE_DIR) / "hrms" / "settings" / "production.py").read_text()
        names = set(re.findall(r"""['"]task['"]:\s*['"]([^'"]+)['"]""", source))
        self.assertTrue(names)
        celery_app.loader.import_default_modules()
        self.assertEqual(names - set(celery_app.tasks), set())


class ShortLeaveAccrualTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.short_leave = LeaveType.objects.create(
            leave_type="Short Leave",
            leave_type_short_code="STL",
            color_hex="#222222",
            accrual_period="MONTHLY",
            accrual_quantity=2,
        )
        self.emp = self.person(7)
        self.now = timezone.now().date()

    def row(self):
        return LeaveBalanceOpenings.objects.get(
            user=self.emp, leave_type=self.short_leave, year=self.now.year, month=self.now.month
        )

    def test_creates_the_new_month(self):
        tasks.accrue_monthly_short_leave()
        self.assertEqual(self.row().remaining_leave_balances, 2)

    def test_a_used_balance_is_left_alone(self):
        tasks.accrue_monthly_short_leave()
        LeaveBalanceOpenings.objects.filter(pk=self.row().pk).update(remaining_leave_balances=1)
        tasks.accrue_monthly_short_leave()
        self.assertEqual(self.row().remaining_leave_balances, 1)
