import json
import logging
from datetime import datetime
from urllib.parse import urlparse
from hrms_app.utility.leave_utils import format_date
from django.utils.http import urlencode
from hrms_app.tasks import send_regularization_notification,send_tour_notifications
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.views.generic import (
    FormView,
    DetailView,
    CreateView,
    TemplateView,
    UpdateView,
    DeleteView,
    ListView,
)
from hrms_app.utility import attendanceutils as at
from hrms_app.hrms.utils import call_soap_api
from hrms_app.hrms.managers import AttendanceStatusHandler
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.sites.models import Site
from django.apps import apps
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django.urls import reverse, reverse_lazy
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.core.files.storage import default_storage
from django.forms.models import model_to_dict
from django.views import View
from django.core.files.base import ContentFile
from django.utils.timezone import now, localtime
from django.contrib.messages.views import SuccessMessageMixin
from django.conf import settings
from django.views.generic.edit import ModelFormMixin
from hrms_app.hrms.filters import AttendanceLogFilter,UserTourFilter
from hrms_app.hrms.form import *
from hrms_app.views.mixins import LeaveListViewMixin
from hrms_app.table_classes import (
    UserTourTable,
    LeaveApplicationTable,
    AttendanceLogTable,
)
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()
logger = logging.getLogger(__name__)
from hrms_app.tasks import push_notification
from hrms_app.views.mixins import LeaveListViewMixin,ModelPermissionRequiredMixin