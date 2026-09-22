"""Tutor 20 integration for settings and Caddy authorization of MFE entry routes."""

from tutor import hooks

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("ACCOUNT_LOCK_ALLOWED_COURSE_IDS", []),
        ("ACCOUNT_LOCK_FALLBACK_URL", "/dashboard"),
    ]
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "openedx-common-settings",
            """
OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = {{ ACCOUNT_LOCK_ALLOWED_COURSE_IDS | tojson }}
OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = {{ ACCOUNT_LOCK_FALLBACK_URL | tojson }}
OPENEDX_ACCOUNT_LOCK_MFE_GATEWAY_ENABLED = True
OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS = [
    "{{ 'https' if ENABLE_HTTPS else 'http' }}://{{ MFE_HOST }}",
]
""",
        ),
        (
            "mfe-caddyfile",
            """
@managed_account_surface path /account /account/* /profile /profile/* /learning/course /learning/course/*
forward_auth @managed_account_surface lms:8000 {
    uri /api/account-lock/v1/authorize
    header_up Host {{ LMS_HOST }}
    header_up X-Account-Lock-Original-Url {{ 'https' if ENABLE_HTTPS else 'http' }}://{host}{uri}
}
""",
        ),
    ]
)
