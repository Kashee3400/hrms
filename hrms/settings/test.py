"""
Tests run on an in-memory SQLite database and never reach a shared one:

    DJANGO_SETTINGS_MODULE=hrms.settings.test python manage.py test hrms_app.tests
"""
from .development import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
# The migrations assume Postgres; the tables are built from the models instead.
MIGRATION_MODULES = {"hrms_app": None}
ALLOWED_HOSTS = ["*"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = "/tmp/hrms_test_media"
