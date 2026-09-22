"""Non-destructive Open edX settings integration."""

from openedx_account_lock_ext.conf import DEFAULTS

MIDDLEWARE = "openedx_account_lock_ext.middleware.AccountLockMiddleware"
ENROLLMENT_FILTER = "org.openedx.learning.course.enrollment.started.v1"
ENROLLMENT_STEP = "openedx_account_lock_ext.filters.AllowlistedEnrollment"


def plugin_settings(settings):
    """Add defaults, middleware, and an enrollment step without replacing operator settings."""
    for key, value in DEFAULTS.items():
        name = "OPENEDX_ACCOUNT_LOCK_" + key
        if not hasattr(settings, name):
            setattr(settings, name, value)
    middleware = list(settings.MIDDLEWARE)
    if MIDDLEWARE not in middleware:
        # A process_view adapter returns the DRF response itself. Run it LAST so it
        # cannot skip another middleware's process_view (CSRF, JWT cookies, etc.).
        # Teak's course RedirectMiddleware handles exceptions, not process_view;
        # restrictions still execute before the course view can redirect.
        middleware.append(MIDDLEWARE)
    settings.MIDDLEWARE = middleware
    filters = dict(getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}))
    config = dict(filters.get(ENROLLMENT_FILTER, {}))
    pipeline = list(config.get("pipeline", []))
    if ENROLLMENT_STEP not in pipeline:
        pipeline.insert(0, ENROLLMENT_STEP)
    config["pipeline"] = pipeline
    config.setdefault("fail_silently", False)
    filters[ENROLLMENT_FILTER] = config
    settings.OPEN_EDX_FILTERS_CONFIG = filters
