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
    'send_reminder_email': {
    'task': 'hrms_app.tasks.send_reminder_email',
    'schedule': crontab(minute=0, hour=10, day_of_month='18-25'),
    },
    'backup_database': {
        'task': 'hrms_app.tasks.backup_database',
        'schedule': crontab(minute=0, hour=3),    
        },
        'calculate-daily-attendance-cache': {
        'task': 'myapp.tasks.calculate_daily_attendance_cache',
        'schedule': crontab(hour=2, minute=0),  # Run at 2:00 AM daily
        'args': (1,)  # Process yesterday's data
    },
    'recalculate-monthly-attendance': {
        'task': 'myapp.tasks.recalculate_monthly_attendance_cache',
        'schedule': crontab(hour=3, minute=0, day_of_month=1),
    },
    "refresh-short-leave-monthly": {
        "task": "leave.tasks.refresh_short_leave_task",
        "schedule": crontab(
            minute=5,
            hour=0,
            day_of_month=1,
        ),
    },
}
