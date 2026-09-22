"""Target-account checks for Teak recovery and confirmation routes."""

from collections.abc import Mapping

from django.apps import apps
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.http import base36_to_int
from django.utils.module_loading import import_string

from .identity import is_locked
from .policy import route_name
from .responses import json_denial

RESET_ROUTES = {"password_reset", "password_change_request"}
TOKEN_ROUTES = {
    "password_reset_confirm",
    "logistration_password_reset",
    "user_api_password_reset_token_validate",
    "user_api_password_reset_token_validate_legacy",
}
EMAIL_MODELS = {
    "confirm_email_change": "PendingEmailChange",
    "activate_secondary_email": "PendingSecondaryEmailChange",
}


def relevant(request):
    """Recognize both anonymous and authenticated recovery endpoints."""
    return route_name(request) in RESET_ROUTES | TOKEN_ROUTES | EMAIL_MODELS.keys()


def _data(request):
    data = getattr(request, "data", None)
    return data if isinstance(data, Mapping) else request.POST


def _reset_target(request):
    user = request.user
    if user.is_authenticated:
        return is_locked(user, request)
    email = _data(request).get("email")
    if not isinstance(email, str) or not email:
        return False
    model = get_user_model()
    users = model._default_manager.filter(  # pylint: disable=protected-access
        **{model.get_email_field_name() + "__iexact": email},
    )
    if any(is_locked(user, request) for user in users):
        return True
    if apps.is_installed("common.djangoapps.student"):
        recovery = apps.get_model("student", "AccountRecovery")
        return any(
            is_locked(row.user, request)
            for row in recovery.objects.filter(
                secondary_email__iexact=email,
            ).select_related("user")
        )
    return False


def response(request, kwargs):
    """Suppress reset initiation, and reject tokens belonging to managed users."""
    name = route_name(request)
    if name in RESET_ROUTES and request.method == "POST" and _reset_target(request):
        # Match Teak's existing generic completion response, including localized markup.
        render_to_string = import_string("common.djangoapps.edxmako.shortcuts.render_to_string")

        result = JsonResponse({"success": True, "value": render_to_string("registration/password_reset_done.html", {})})
        result["Cache-Control"] = "no-store, private"
        return result
    if name in TOKEN_ROUTES:
        identifier = kwargs.get("uidb36")
        if identifier is None:
            token = _data(request).get("token", "")
            identifier = token.split("-", 1)[0] if isinstance(token, str) else ""
        try:
            pk = base36_to_int(identifier)
            user = get_user_model()._default_manager.filter(pk=pk).first()  # pylint: disable=protected-access
        except (TypeError, ValueError, OverflowError):
            return None  # Preserve the platform's invalid-token behavior.
        if is_locked(user, request):
            return json_denial()
    if name in EMAIL_MODELS:
        model = apps.get_model("student", EMAIL_MODELS[name])
        pending = model.objects.select_related("user").filter(activation_key=kwargs.get("key")).first()
        if pending and is_locked(pending.user, request):
            return json_denial()
    return None
