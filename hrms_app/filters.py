import django_filters
from django.contrib.auth import get_user_model
from .models import UserTour

class UserTourFilter(django_filters.FilterSet):
    # Define your filter fields here
    applied_by = django_filters.ModelChoiceFilter(queryset=get_user_model().objects.all())
    
    class Meta:
        model = UserTour
        fields = ['applied_by']

