import django_filters
from hrms_app.models import AttendanceLog,UserTour
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.conf import settings
from django import forms
from django.utils.translation import gettext_lazy as _
User = get_user_model()


class AttendanceLogFilter(django_filters.FilterSet):
    class Meta:
        model = AttendanceLog
        fields = {
            'applied_by': ['exact'],
            'reg_status': ['exact'],
            'is_submitted': ['exact']
        }


class UserTourFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=settings.TOUR_STATUS_CHOICES,
        empty_label="All",
        default=settings.PENDING,
        label="Status",
    )
    from_date = django_filters.DateFilter(
        field_name="start_date",
        lookup_expr="gte",
        label="From Date",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    to_date = django_filters.DateFilter(
        field_name="end_date",
        lookup_expr="lte",
        label="To Date",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = UserTour
        fields = ["status", "from_date", "to_date", "search"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(applied_by__username__icontains=value)
            | Q(applied_by__first_name__icontains=value)
            | Q(applied_by__last_name__icontains=value)
            | Q(from_destination__icontains=value)
            | Q(to_destination__icontains=value)
        )
