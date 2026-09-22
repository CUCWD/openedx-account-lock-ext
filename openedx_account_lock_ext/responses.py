"""Safe redirects for pages and stable JSON denials for APIs."""

from urllib.parse import unquote, urlsplit

from django.contrib import messages
from django.http import HttpRequest, JsonResponse, QueryDict
from django.shortcuts import redirect
from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme

from . import conf, courses, policy

DETAIL = "This account cannot access this resource."
WARNING = "This page is restricted for managed accounts."


def json_denial():
    """Create the public, stable error representation."""
    response = JsonResponse({"error": "account_locked", "detail": DETAIL}, status=403)
    response["Cache-Control"] = "no-store, private"
    return response


def is_api(request):
    """Recognize APIs, AJAX and XBlock handlers even outside /api/."""
    return (
        request.path_info.startswith(("/api/", "/user_api/"))
        or "/handler" in request.path_info
        or request.method not in {"GET", "HEAD"}
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def safe_destination(request, destination):
    """Reject unsafe hosts, blocked destinations and self-referral loops."""
    # Independent early rejections keep the redirect security checks explicit.
    # pylint: disable=too-many-return-statements
    if not destination or not url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return False
    try:
        parsed = urlsplit(destination)
    except ValueError:
        return False
    path = unquote(parsed.path) or "/"
    if not path.startswith("/") or conf.normalized(path) == conf.normalized(request.path_info):
        return False
    if conf.matches_any(path, (*conf.get("RESTRICTED_PAGE_PATHS"), "/account")) or policy.account_api(path):
        return False
    # Never bounce to an unverified course or another API. This avoids restriction loops.
    if path.startswith(("/api/", "/user_api/")):
        return False
    try:
        kwargs = resolve(path).kwargs
    except Resolver404:
        kwargs = {}
    candidate = HttpRequest()
    candidate.path_info = path
    candidate.method = "GET"
    candidate.GET = QueryDict(parsed.query)
    if courses.denied(candidate, kwargs):
        return False
    return True


def blocked(request):
    """Deny JSON requests or redirect HTML requests with a warning."""
    if is_api(request):
        return json_denial()
    destination = request.META.get("HTTP_REFERER")
    if not safe_destination(request, destination):
        destination = conf.get("FALLBACK_URL")
    if not safe_destination(request, destination):
        destination = "/dashboard"
    if not safe_destination(request, destination):
        return json_denial()
    messages.warning(request, WARNING)
    response = redirect(destination)
    response["Cache-Control"] = "no-store, private"
    return response
