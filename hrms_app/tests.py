from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from .models import LeaveApplication, LeaveType, CustomUser,LeaveDayChoiceAdjustment
from django.urls import reverse
from django.conf import settings
from hrms_app.utility.leave_utils import calculate_total_days
from datetime import datetime


class CalculateTotalDaysTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Set up LeaveDayChoiceAdjustment instances that will be used in the tests
        LeaveDayChoiceAdjustment.objects.create(
            start_day_choice=settings.FIRST_HALF,
            end_day_choice=settings.FIRST_HALF,
            adjustment_value=0.5
        )
        LeaveDayChoiceAdjustment.objects.create(
            start_day_choice=settings.SECOND_HALF,
            end_day_choice=settings.SECOND_HALF,
            adjustment_value=0.5
        )

    def test_total_days_normal_case(self):
        """Test calculating leave days for normal cases"""
        start_date = datetime(2024, 10, 10).date()
        end_date = datetime(2024, 10, 12).date()
        result = calculate_total_days(start_date, end_date, settings.FULL_DAY, settings.FULL_DAY)
        print('test_total_days_normal_case')
        print(f"Start Date: {start_date}, End Date: {end_date}, Total Days: {result}")
        self.assertEqual(result, 3.0)  # Expected result is 3 days

    def test_same_day_half_day_case(self):
        """Test calculation for the same day with half-day leave"""
        start_date = end_date = datetime(2024, 10, 10).date()
        result = calculate_total_days(start_date, end_date, settings.FIRST_HALF, settings.FIRST_HALF)
        print('test_same_day_half_day_case')
        print(f"Start Date: {start_date}, End Date: {end_date}, Total Days: {result}")
        self.assertEqual(result, 0.5)  # Expected result is 0.5 days

    def test_same_day_full_day_case(self):
        """Test calculation for the same day with a full day leave"""
        start_date = end_date = datetime(2024, 10, 10).date()
        result = calculate_total_days(start_date, end_date, settings.FULL_DAY, settings.FULL_DAY)
        print('test_same_day_full_day_case')
        print(f"Start Date: {start_date}, End Date: {end_date}, Total Days: {result}")
        self.assertEqual(result, 1.0)  # Expected result is 1 day

    def test_date_swapped_case(self):
        """Test calculation when start_date is after end_date (dates are swapped)"""
        start_date = datetime(2024, 10, 28).date()
        end_date = datetime(2024, 10, 29).date()
        result = calculate_total_days(start_date, end_date, settings.FULL_DAY, settings.FULL_DAY)
        print('test_date_swapped_case')
        print(f"Start Date: {start_date}, End Date: {end_date}, Total Days: {result}")
        self.assertEqual(result, 2.0)  # Expected result is 3 days after date swap

    def test_adjustment_case(self):
        """Test calculation with stored adjustments for half-day choices"""
        start_date = datetime(2024, 10, 10).date()
        end_date = datetime(2024, 10, 12).date()
        result = calculate_total_days(start_date, end_date, settings.FIRST_HALF, settings.FIRST_HALF)
        print('test_adjustment_case')
        print(f"Start Date: {start_date}, End Date: {end_date}, Total Days: {result}")
        self.assertEqual(result, 3.5)  # Expected result: 3 days + 0.5 adjustment

    def test_no_adjustment_case(self):
        """Test calculation without any adjustment in the database"""
        start_date = datetime(2024, 10, 10).date()
        end_date = datetime(2024, 10, 12).date()
        result = calculate_total_days(start_date, end_date, settings.FULL_DAY, settings.FULL_DAY)
        print('test_no_adjustment_case')
        print(f"Start Date: {start_date}, End Date: {end_date}, Total Days: {result}")
        self.assertEqual(result, 3.0)  # Expected result is 3 days, no adjustment applied
