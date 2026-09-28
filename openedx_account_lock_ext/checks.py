"""Fail configuration checks when security-critical integration is incomplete."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import CheckMessage, Error
from django.core.checks import Warning as CheckWarning
from django.core.checks import register
from django.utils.module_loading import import_string

from . import conf, courses
from .settings.common import ENROLLMENT_FILTER, ENROLLMENT_STEP, MIDDLEWARE


@register()
def account_lock_checks(app_configs, **kwargs):  # pylint: disable=unused-argument
    """Validate course configuration, safe redirects and middleware/filter ordering."""
    # Configuration errors are deliberately accumulated rather than failing at the first one.
    # pylint: disable=too-many-branches
    errors: list[CheckMessage] = []
    for course in conf.get("ALLOWED_COURSE_IDS"):
        try:
            courses.canonical(course)
        except courses.UnresolvedCourse:
            errors.append(Error(f"Invalid managed course ID: {course}", id="account_lock.E001"))
    fallback = conf.get("FALLBACK_URL")
    try:
        parsed = urlsplit(fallback)
        path = parsed.path
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        is_local_path = (
            fallback.startswith("/")
            and not fallback.startswith("//")
            and not parsed.netloc
            and not parsed.scheme
        )
        is_configured_mfe_url = (
            origin in set(conf.get("MFE_ORIGINS"))
            and parsed.scheme in {"http", "https"}
            and bool(path)
        )
        valid = (
            (is_local_path or is_configured_mfe_url)
            and "\\" not in fallback
            and path.startswith("/")
            and not conf.matches_any(path, conf.get("RESTRICTED_PAGE_PATHS"))
            and not conf.matches_any(path, conf.get("RESTRICTED_API_PREFIXES"))
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        errors.append(
            Error(
                "Fallback must be a safe, unrestricted local path or configured MFE URL.",
                id="account_lock.E002",
            )
        )
    middleware = list(settings.MIDDLEWARE)
    if MIDDLEWARE not in middleware:
        errors.append(Error("Managed account middleware is missing.", id="account_lock.E003"))
    else:
        index = middleware.index(MIDDLEWARE)
        for suffix in ("SessionMiddleware", "AuthenticationMiddleware", "MessageMiddleware"):
            if not any(name.endswith(suffix) for name in middleware[:index]):
                errors.append(Error(f"Account lock must follow {suffix}.", id="account_lock.E004"))
        following_view_middleware = [
            name
            for name in middleware[index + 1:]
            if hasattr(import_string(name), "process_view")
        ]
        if following_view_middleware:
            errors.append(
                Error(
                    "Account lock must follow middleware with process_view hooks: "
                    + ", ".join(following_view_middleware),
                    id="account_lock.E004",
                )
            )
    pipeline = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}).get(ENROLLMENT_FILTER, {})
    if ENROLLMENT_STEP not in pipeline.get("pipeline", []) or pipeline.get("fail_silently", False):
        errors.append(Error("The enrollment guard must be configured and fail_silently=False.", id="account_lock.E005"))
    if conf.get("REQUIRE_MFE_GATEWAY") and not conf.get("MFE_GATEWAY_ENABLED"):
        errors.append(Error("Configure a gateway for independently served MFEs.", id="account_lock.E006"))
    if conf.get("MFE_GATEWAY_ENABLED") and not conf.get("MFE_ORIGINS"):
        errors.append(Error("Configure the exact MFE origins, including development ports.", id="account_lock.E007"))
    if not conf.get("ALLOWED_COURSE_IDS"):
        errors.append(
            CheckWarning("Locked accounts cannot access any courses until configured.", id="account_lock.W001")
        )
    return errors
