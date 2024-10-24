from .base import *

STATIC_DIR = os.path.join(BASE_DIR,'static')

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

STATICFILES_DIRS = [STATIC_DIR]