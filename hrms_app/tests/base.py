"""Shared set-up for the mobile API tests."""
import itertools
from datetime import datetime, timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hrms_app.models import (
    CustomUser,
    Department,
    Designation,
    LeaveApplication,
    LeaveType,
    OfficeLocation,
    PersonalDetails,
    UserTour,
)

_serial = itertools.count(1)


def at(day, hour=9):
    return timezone.make_aware(datetime(day.year, day.month, day.day, hour))


class MobileTestCase(TestCase):
    """Push is switched off; everything else runs for real."""

    @classmethod
    def setUpClass(cls):
        # CurrentRequestMiddleware leaves the last request here, and saves
        # read their created_by from it.
        settings.CURRENT_REQUEST = None
        super().setUpClass()

    @classmethod
    def setUpTestData(cls):
        cls.location = OfficeLocation.objects.create(location_name="HO")
        cls.ops = Department.objects.create(department="ops")
        cls.admin_department = Department.objects.create(department="admin")
        cls.exec_designation = Designation.objects.create(designation="Exec", department=cls.ops)
        cls.admin_designation = Designation.objects.create(designation="Admin", department=cls.admin_department)
        cls.casual = LeaveType.objects.create(leave_type="Casual", leave_type_short_code="CL", color_hex="#000EB0")
        cls.lwp = LeaveType.objects.create(leave_type="Without Pay", leave_type_short_code="LWP", color_hex="#111111")

    def setUp(self):
        patcher = mock.patch("hrms_app.tasks.send_notification_push")
        patcher.start()
        self.addCleanup(patcher.stop)

    def person(self, number, designation=None, password="x", **extra):
        settings.CURRENT_REQUEST = None
        code = str(number)
        user = CustomUser.objects.create_user(
            username=f"KMPCL-{number:03}",
            password=password,
            first_name=f"P{number}",
            last_name="Name",
            device_location=self.location,
            **extra,
        )
        PersonalDetails.objects.create(
            user=user,
            designation=designation or self.exec_designation,
            doj="2020-01-01",
            employee_code=code,
            mobile_number=code,
            official_mobile_number=code,
            alt_mobile_number=code,
            cug_mobile_number=code,
            birthday="1990-01-01",
        )
        return CustomUser.objects.get(pk=user.pk)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def leave(self, user, day, status, kind=None, days=1):
        """Bypasses the save hooks: tests set up state, not the apply flow."""
        serial = next(_serial)
        LeaveApplication.objects.bulk_create(
            [
                LeaveApplication(
                    leave_type=kind or self.casual,
                    appliedBy=user,
                    startDate=at(day),
                    endDate=at(day + timedelta(days - 1), 18),
                    usedLeave=days,
                    balanceLeave=5,
                    reason="r",
                    status=status,
                    startDayChoice="1",
                    endDayChoice="1",
                    slug=f"leave-{serial}",
                    applicationNo=f"APP-{serial}",
                )
            ]
        )
        return LeaveApplication.objects.get(slug=f"leave-{serial}")

    def tour(self, user, start, end, status, extended=None):
        serial = next(_serial)
        UserTour.objects.bulk_create(
            [
                UserTour(
                    applied_by=user,
                    from_destination="A",
                    to_destination="B",
                    start_date=start,
                    end_date=end,
                    start_time="09:00",
                    end_time="18:00",
                    status=status,
                    extended_end_date=extended,
                    slug=f"tour-{serial}",
                )
            ]
        )
        return UserTour.objects.get(slug=f"tour-{serial}")
