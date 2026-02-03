from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hrms_app.models import LeaveType, LeaveBalanceOpenings, CustomUser
from hrms_app.choices.leave import LeaveAccrualPeriod


class Command(BaseCommand):
    help = "Accrue monthly short leave for all active users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="Year for accrual (default: current year)",
        )
        parser.add_argument(
            "--month",
            type=int,
            help="Month for accrual (1-12) (default: current month)",
        )

    def handle(self, *args, **options):
        today = timezone.now().date()

        year = options.get("year") or today.year
        month = options.get("month") or today.month

        # Validate month
        if month < 1 or month > 12:
            self.stdout.write(self.style.ERROR("Month must be between 1 and 12."))
            return

        monthly_leave_types = LeaveType.objects.filter(
            accrual_period=LeaveAccrualPeriod.MONTHLY,
            accrual_quantity__gt=0,
        )

        if not monthly_leave_types.exists():
            self.stdout.write(self.style.WARNING("No monthly leave types found."))
            return

        users = CustomUser.objects.filter(is_active=True)

        created_count = 0

        with transaction.atomic():

            for leave_type in monthly_leave_types:
                qty = leave_type.accrual_quantity

                for user in users:
                    balance, created = LeaveBalanceOpenings.objects.get_or_create(
                        user=user,
                        leave_type=leave_type,
                        year=year,
                        month=month,
                        defaults={
                            "no_of_leaves":qty,
                            "opening_balance": qty,
                            "allocated": qty,
                            "remaining_leave_balances": qty,
                            "closing_balance": qty,
                        },
                    )

                    if created:
                        created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Monthly short leave accrual completed for {year}-{month}. "
                f"{created_count} balances created."
            )
        )

