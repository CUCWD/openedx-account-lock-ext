"""Request-scoped safeguard against web-based managed credential changes."""

from contextvars import ContextVar

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models.signals import pre_save

from .identity import is_locked

current_request = ContextVar("account_lock_request", default=None)


def protect_credentials(sender, instance, using, **kwargs):
    """Permit existing managed credentials to change only offline or through admin."""
    request = current_request.get()
    if request is None or not instance.pk or kwargs.get("raw"):
        return
    match = getattr(request, "resolver_match", None)
    actor = getattr(request, "user", None)
    if match and "admin" in match.namespaces and actor and actor.is_active and actor.is_staff:
        return
    email_field = sender.get_email_field_name()
    original = sender._default_manager.using(using).filter(pk=instance.pk).first()  # pylint: disable=protected-access
    if original is None:
        return
    fields = kwargs.get("update_fields")
    changed = any(
        (fields is None or field in fields) and getattr(original, field) != getattr(instance, field)
        for field in ("password", email_field)
    )
    if changed and is_locked(original, request):
        raise PermissionDenied("Managed credentials can only be changed by an administrator.")


def connect():
    """Register once for the configured user model, not Django's concrete User."""
    pre_save.connect(
        protect_credentials,
        sender=get_user_model(),
        weak=False,
        dispatch_uid="openedx_account_lock_ext.protect_credentials",
    )
