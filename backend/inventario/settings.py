import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("INVENTARIO_DATA_DIR", BASE_DIR / "data"))

SECRET_KEY = os.environ.get("SESSION_SECRET", "local-only-session-key")
DEBUG = False
# This package is designed for trusted local networks. The Django development
# server binds to the host's LAN interfaces so other devices can connect.
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "api",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "inventario.urls"
WSGI_APPLICATION = "inventario.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "inventario.sqlite3",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"

STATIC_URL = "/static/"
APPEND_SLASH = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = False
TIME_ZONE = "America/Bogota"
LANGUAGE_CODE = "es-co"
