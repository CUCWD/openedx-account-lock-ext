"""Separate-process settings for custom user model tests."""

from tests.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "tests.customapp"]  # noqa: F405
AUTH_USER_MODEL = "customapp.EmailUser"
MIGRATION_MODULES = {"customapp": None}
