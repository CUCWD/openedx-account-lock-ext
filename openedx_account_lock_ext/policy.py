"""Account route decisions independent of response transport."""

import re

from . import conf, courses
from .identity import is_locked

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ACCOUNT_ROUTES = {
    "change_email_settings",
    "confirm_email_change",
    "activate_secondary_email",
    "request_name_change",
    "confirm_name_change",
    "accounts_deactivation",
}


def route_name(request):
    """Return the unnamespaced Django route name when available."""
    match = getattr(request, "resolver_match", None)
    return getattr(match, "url_name", None)


def account_api(path):
    """Match configured account APIs including slashless roots."""
    mobile_identity = re.fullmatch(r"/api/mobile/[^/]+/(?:my_user_info|users/[^/]+)/?", path)
    return bool(mobile_identity) or conf.matches_any(path, conf.get("RESTRICTED_API_PREFIXES"))


def bootstrap(request):
    """Allow only the authenticated user's exact account bootstrap endpoint."""
    username = request.user.get_username()
    return (
        request.method in {"GET", "HEAD"} and conf.normalized(request.path_info) == f"/api/user/v1/accounts/{username}"
    )


def read_exception(request):
    """Allow narrowly scoped reads needed for frontend authentication/localization."""
    if bootstrap(request):
        return True
    return request.method in {"GET", "HEAD"} and any(
        conf.normalized(request.path_info) == f"/api/user/v1/preferences/{request.user.get_username()}/{key}"
        for key in conf.get("READ_PREFERENCE_KEYS")
    )


def denied(request, kwargs):
    """Apply managed-account restrictions after authentication."""
    if not is_locked(request.user, request):
        return False
    path = request.path_info
    if conf.matches_any(path, conf.get("RESTRICTED_PAGE_PATHS")):
        return True
    if route_name(request) in ACCOUNT_ROUTES:
        return True
    if account_api(path):
        if request.method == "OPTIONS":
            return False
        return not read_exception(request)
    return courses.denied(request, kwargs)


def relevant(request, kwargs):
    """Identify views that need authentication-aware enforcement."""
    return (
        account_api(request.path_info)
        or conf.matches_any(request.path_info, conf.get("RESTRICTED_PAGE_PATHS"))
        or route_name(request) in ACCOUNT_ROUTES
        or courses.protected(request, kwargs)
    )
