import django_filters
from django.contrib.auth import get_user_model
from django.conf import settings
from django_filters import rest_framework as filters
from .models import Notification,UserTour
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import LeaveType


class UserTourFilter(django_filters.FilterSet):
    # Define your filter fields here
    applied_by = django_filters.ModelChoiceFilter(queryset=get_user_model().objects.all())
    
    class Meta:
        model = UserTour
        fields = ['applied_by']



class NotificationFilter(filters.FilterSet):
    """
    FilterSet for Notification model to filter by timestamp.
    """
    from_date = filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="gte")
    to_date = filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = Notification
        fields = ["from_date", "to_date"]



class LeaveAllocationFilter(admin.SimpleListFilter):
    title = _('Has Accrual')
    parameter_name = 'has_accrual'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('With Accrual')),
            ('no', _('Without Accrual')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(accrual_period='NONE')
        if self.value() == 'no':
            return queryset.filter(accrual_period='NONE')
        return queryset


class LeaveUnitFilter(admin.SimpleListFilter):
    title = _('Leave Unit')
    parameter_name = 'leave_unit'

    def lookups(self, request, model_admin):
        return LeaveType._meta.get_field('leave_unit').choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(leave_unit=self.value())
        return queryset

