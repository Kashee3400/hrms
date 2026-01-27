from django.db import models
from django.conf import settings

class LeaveDayQuerySet(models.QuerySet):

    def approved(self):
        return self.filter(
            leave_application__status=settings.APPROVED
        )

    def stl(self):
        """
        Filter Short Leave (STL) leave days
        """
        return self.filter(
            leave_application__leave_type__leave_type_short_code="STL"
        )

    def non_stl(self):
        """
        Filter non-STL leave days
        """
        return self.exclude(
            leave_application__leave_type__leave_type_short_code="STL"
        )

    def for_employees(self, employee_ids):
        return self.filter(
            leave_application__appliedBy_id__in=employee_ids
        )

    def between_dates(self, start_date, end_date):
        if start_date and end_date:
            return self.filter(date__range=[start_date, end_date])
        return self


class LeaveDayManager(models.Manager):
    def get_queryset(self):
        return LeaveDayQuerySet(self.model, using=self._db)

    def stl_leave_days(self, employee_ids, start_date=None, end_date=None):
        return (
            self.get_queryset()
            .approved()
            .stl()
            .for_employees(employee_ids)
            .between_dates(start_date, end_date)
        )

    def non_stl_leave_days(self, employee_ids, start_date=None, end_date=None):
        return (
            self.get_queryset()
            .approved()
            .non_stl()
            .for_employees(employee_ids)
            .between_dates(start_date, end_date)
        )
        
    def approved(self):
        return self.get_queryset().approved()
