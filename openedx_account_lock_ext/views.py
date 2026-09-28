"""Authorization endpoint for the MFE gateway; it does not convey user identity."""

from urllib.parse import unquote, urlsplit

from django.http import HttpRequest, HttpResponse, QueryDict
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from . import conf, courses
from .identity import is_locked
from .responses import json_denial, mfe_gateway_blocked


class GatewayAuthorization(APIView):
    """Authorize the original MFE URL using normal LMS request authentication."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return 204 to continue serving, or uncached JSON 403 to stop serving."""
        # Early returns keep malformed-URL and authorization rejection paths explicit.
        # pylint: disable=too-many-return-statements
        original_url = request.headers.get("X-Account-Lock-Original-Url", "")
        try:
            parsed = urlsplit(original_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            valid = (
                origin in conf.get("MFE_ORIGINS")
                and parsed.scheme in {"http", "https"}
                and not parsed.username
                and not parsed.password
                and not parsed.fragment
                and "\\" not in original_url
            )
        except ValueError:
            valid = False
        if not valid:
            return json_denial()
        if is_locked(request.user, request):
            path = unquote(parsed.path)
            if "\\" in path or "%" in path or any(part in {".", ".."} for part in path.split("/")):
                return json_denial()
            if conf.matches_any(path, ("/account", "/profile")):
                return mfe_gateway_blocked(request)
            if conf.matches(path, "/learning/course"):
                candidate = HttpRequest()
                candidate.path_info = path
                candidate.method = "GET"
                candidate.GET = QueryDict(parsed.query)
                try:
                    if not courses.allowed(courses.resolve(candidate, {})):
                        return mfe_gateway_blocked(request)
                except courses.UnresolvedCourse:
                    return mfe_gateway_blocked(request)
            else:
                # Caddy may normalize paths differently (case, repeated slashes).
                # This endpoint authorizes only the specifically gated surfaces.
                return mfe_gateway_blocked(request)
        response = HttpResponse(status=204)
        response["Cache-Control"] = "no-store, private"
        response["Vary"] = "Cookie, Authorization"
        return response
