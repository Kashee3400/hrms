from .base import *

DEBUG  = False
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Behind nginx (TLS terminates there). nginx always overwrites
# X-Forwarded-Proto, so clients can't spoof it.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Django 4 rejects HTTPS form posts (login included) from origins not listed.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if o.strip()
]
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)

# Static files are collected into the Docker image and served by WhiteNoise.
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    "handlers": {
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        }
    },
    "loggers": {
        "django.request": {
            "handlers": ["mail_admins"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}

STATIC_ROOT = os.path.join(BASE_DIR, "static")

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'send_wishing_email': {
        'task': 'hrms_app.tasks.send_greeting_emails',
        'schedule': crontab(minute=0, hour=9),  # Every day at 9:00 AM
    },
    'populate_attendance_log': {
        'task': 'hrms_app.tasks.populate_attendance_log',
        'schedule': crontab(minute=59, hour=22),
    },
    'scan_attendance_gaps': {
        'task': 'hrms_app.tasks.scan_attendance_gaps',
        'schedule': crontab(minute=30, hour=9, day_of_week='mon-sat'),
    },
    'check_attendance_gap_engine': {
        'task': 'hrms_app.tasks.check_attendance_gap_engine',
        'schedule': crontab(minute=0, hour=11, day_of_week='mon-sat'),
    },
    'send_approval_reminders': {
        'task': 'hrms_app.tasks.send_approval_reminders',
        'schedule': crontab(minute=30, hour=10, day_of_week='mon-sat'),
    },
    'remove_expired_allowed_users': {
        'task': 'hrms_app.tasks.remove_expired_allowed_users',
        'schedule': crontab(minute=15, hour=0),
    },
    'send_reminder_email': {
    'task': 'hrms_app.tasks.send_reminder_email',
    'schedule': crontab(minute=0, hour=10, day_of_month='18-25'),
    },
    'backup_database': {
        'task': 'hrms_app.tasks.backup_database',
        'schedule': crontab(minute=0, hour=3),    
        },
    "accrue-monthly-short-leave": {
        "task": "hrms_app.tasks.accrue_monthly_short_leave",
        "schedule": crontab(
            minute=5,
            hour=0,
            day_of_month=1,
        ),
    },
}
