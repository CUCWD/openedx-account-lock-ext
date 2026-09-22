"""Minimal real Django/DRF runtime for standalone plugin tests."""

import sys

from openedx_account_lock_ext.settings.common import plugin_settings

SECRET_KEY = "test-only-secret"
JWT_AUTH = {
    "JWT_SECRET_KEY": "test-only-jwt-secret-at-least-32-bytes",
    "JWT_ALGORITHM": "HS256",
    "JWT_AUTH_HEADER_PREFIX": "JWT",
    "JWT_AUTH_COOKIE": "edx-jwt-cookie",
    "JWT_AUTH_COOKIE_HEADER_PAYLOAD": "edx-jwt-cookie-header-payload",
    "JWT_AUTH_COOKIE_SIGNATURE": "edx-jwt-cookie-signature",
}
ALLOWED_HOSTS = ["testserver", "lms.example.org"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "openedx_account_lock_ext",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "tests.urls"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}]
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["tests.auth.HeaderAuthentication"]}
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
USE_TZ = True
OPENEDX_TELEMETRY = []
OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = ["course-v1:Demo+Allowed+2026"]
OPENEDX_ACCOUNT_LOCK_MFE_GATEWAY_ENABLED = True
OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS = ["https://apps.example.org"]

plugin_settings(sys.modules[__name__])
