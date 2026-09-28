"""Operator configuration, read lazily to support Django settings overrides."""

from django.conf import settings

GROUP = "locked_account"
DEFAULTS = {
    "ALLOWED_COURSE_IDS": (),
    "FALLBACK_URL": "/learner-dashboard/",
    "RESTRICTED_PAGE_PATHS": ("/account/settings", "/account/password", "/account/email", "/profile"),
    "RESTRICTED_API_PREFIXES": (
        "/api/user/v1/accounts/",
        "/api/user/v1/preferences/",
        "/api/user/v2/account/password",
        "/api/user/v2/account/email",
        "/api/user/v2/account/name",
        "/api/user/v2/account/profile",
        "/api/profile_images/",
        "/api/change_email_settings",
    ),
    "READ_PREFERENCE_KEYS": ("pref-lang", "time_zone"),
    "BOOTSTRAP_FIELDS": ("username", "name", "profile_image"),
    "MFE_ORIGINS": (),
    "REQUIRE_MFE_GATEWAY": True,
    "MFE_GATEWAY_ENABLED": False,
    "COURSE_RESOLVERS": (),
    "COURSE_NUMBER_MAP": {},
    "COURSE_API_PREFIXES": (
        "/api/course_home",
        "/api/courseware",
        "/api/course_experience",
        "/api/course_structure",
        "/api/grades",
        "/api/enrollment/v1",
        "/api/discussion",
        "/api/discussions",
        "/api/xblock",
        "/api/bookmarks",
        "/api/completion",
        "/api/progress",
        "/api/edx_proctoring",
        "/api/credit",
        "/api/course_goals",
        "/api/ccx",
        "/api/ora",
        "/api/learner_home",
        "/api/learner_dashboard",
        "/api/keyterms",
    ),
}


def get(name):
    """Return a namespaced setting or its documented default."""
    return getattr(settings, "OPENEDX_ACCOUNT_LOCK_" + name, DEFAULTS[name])


def normalized(path):
    """Normalize trailing slashes, preserving all other path boundaries."""
    return path.rstrip("/") or "/"


def matches(path, prefix):
    """Match a path and descendants without matching similarly named siblings."""
    path, prefix = normalized(path), normalized(prefix)
    return path == prefix or path.startswith(prefix + "/")


def matches_any(path, prefixes):
    """Apply boundary-aware matching to a sequence of configured prefixes."""
    return any(matches(path, prefix) for prefix in prefixes)
