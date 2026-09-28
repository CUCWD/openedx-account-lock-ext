"""Configuration checks and nondestructive registration."""

from types import SimpleNamespace

import pytest
from jinja2 import Environment, StrictUndefined

from openedx_account_lock_ext.checks import account_lock_checks
from openedx_account_lock_ext.settings.common import ENROLLMENT_FILTER, ENROLLMENT_STEP, MIDDLEWARE, plugin_settings


def test_valid_configuration():
    """The complete fixture deployment passes security checks."""
    assert not account_lock_checks(None)


@pytest.mark.parametrize(
    "value,code",
    [
        (["not-a-course"], "account_lock.E001"),
        ([], "account_lock.W001"),
    ],
)
def test_invalid_courses(settings, value, code):
    """Invalid IDs and empty allowlists are made visible to operators."""
    settings.OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = value
    assert code in {error.id for error in account_lock_checks(None)}


@pytest.mark.parametrize(
    "fallback",
    [
        "//evil.test/",
        "https://evil.test",
        "https://apps.example.org:1996/profile",
        "/profile",
        "/api/user/v1/accounts",
    ],
)
def test_unsafe_fallback(settings, fallback):
    """Bad fallbacks fail checks before deployment."""
    settings.OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = fallback
    assert "account_lock.E002" in {error.id for error in account_lock_checks(None)}


def test_configured_mfe_fallback(settings):
    """Development may use the allowlisted learner-dashboard MFE origin."""
    settings.OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS = [
        "https://apps.example.org",
        "https://apps.example.org:1996",
    ]
    settings.OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = "https://apps.example.org:1996/learner-dashboard/"
    assert "account_lock.E002" not in {error.id for error in account_lock_checks(None)}


def test_missing_integrations(settings):
    """Middleware, enrollment filtering, and gateway protection are required."""
    settings.MIDDLEWARE = []
    settings.OPEN_EDX_FILTERS_CONFIG = {}
    settings.OPENEDX_ACCOUNT_LOCK_MFE_GATEWAY_ENABLED = False
    assert {"account_lock.E003", "account_lock.E005", "account_lock.E006"} <= {
        error.id for error in account_lock_checks(None)
    }


def test_idempotent_registration():
    """Preserve existing filters and register exactly once after authentication/CORS."""
    settings = SimpleNamespace(
        MIDDLEWARE=[
            "x.SessionMiddleware",
            "x.AuthenticationMiddleware",
            "x.MessageMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "lms.djangoapps.courseware.middleware.RedirectMiddleware",
        ],
        OPEN_EDX_FILTERS_CONFIG={ENROLLMENT_FILTER: {"pipeline": ["existing.step"]}},
    )
    plugin_settings(settings)
    plugin_settings(settings)
    assert settings.MIDDLEWARE.count(MIDDLEWARE) == 1
    assert settings.MIDDLEWARE.index(MIDDLEWARE) == 5
    assert settings.OPEN_EDX_FILTERS_CONFIG[ENROLLMENT_FILTER]["pipeline"] == [ENROLLMENT_STEP, "existing.step"]


def test_tutor_patch_rendering():
    """Render actual Tutor patch registrations without touching the user's Tutor root."""
    from tutor import hooks

    from tutoraccountlock import plugin  # noqa: F401

    patches = list(hooks.Filters.ENV_PATCHES.iterate())
    template = next(text for name, text in patches if name == "mfe-caddyfile" and "managed_account_surface" in text)
    result = (
        Environment(undefined=StrictUndefined)
        .from_string(template)
        .render(
            ENABLE_HTTPS=True,
            LMS_HOST="learn.example.org",
        )
    )
    assert "forward_auth @managed_account_surface lms:8000" in result
    assert "header_up Host learn.example.org" in result
    assert "X-Account-Lock-Original-Url https://{host}{uri}" in result
