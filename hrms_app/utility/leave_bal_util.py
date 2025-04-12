from datetime import datetime
from django.contrib.auth import get_user_model
from collections import defaultdict
from django.conf import settings
from django.utils.translation import gettext_lazy as _

User = get_user_model()
from django.utils.timezone import make_aware, localtime, utc
from datetime import datetime, timedelta
from hrms_app.utility import attendanceutils as at


