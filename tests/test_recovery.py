"""Recovery tokens and the request-scoped credential safeguard."""

import sys
from types import ModuleType, SimpleNamespace

import pytest
from django.utils.http import int_to_base36

from openedx_account_lock_ext import recovery
from openedx_account_lock_ext.credentials import current_request

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("prefix", ["password_reset_confirm", "password/reset"])
def test_anonymous_reset_token(client, locked, prefix):
    """Even a previously issued token cannot change a managed account's password."""
    response = client.post(f"/{prefix}/{int_to_base36(locked.pk)}-existing-token/", {"new_password": "another"})
    assert response.status_code == 403
    assert response.json()["error"] == "account_locked"
    locked.refresh_from_db()
    assert locked.check_password("testing-password")


def test_reset_initiation_generic(client, locked, monkeypatch):
    """Suppressed reset mail preserves Teak's generic localized completion shape."""
    module = ModuleType("common.djangoapps.edxmako.shortcuts")
    module.render_to_string = lambda *args: "generic completion"
    monkeypatch.setitem(sys.modules, module.__name__, module)
    response = client.post("/password_reset/", {"email": locked.email})
    assert response.status_code == 200
    assert response.json() == {"success": True, "value": "generic completion"}
    assert "rendered" not in response.json()


def test_unregistered_web_mutation(client, locked):
    """The save safeguard covers web changes outside the route registry."""
    assert client.post("/credentials").status_code == 403
    locked.refresh_from_db()
    assert locked.check_password("testing-password")
    assert current_request.get() is None


def test_admin_change(client, locked, django_user_model):
    """Authorized admin saves and offline management saves remain available."""
    admin = django_user_model.objects.create_superuser("admin", "admin@example.org", "password")
    client.force_login(admin)
    assert client.post("/admin/credentials").status_code == 200
    locked.refresh_from_db()
    assert locked.check_password("unauthorized-password")
    locked.set_password("offline-administrator-password")
    locked.save()
    locked.refresh_from_db()
    assert locked.check_password("offline-administrator-password")


def test_context_cleanup(client):
    """Context never escapes the request lifetime."""
    assert client.get("/scope").json() == {"active": True}
    assert current_request.get() is None


@pytest.mark.parametrize("name", ["confirm_email_change", "activate_secondary_email"])
def test_pending_email_target(rf, locked, monkeypatch, name):
    """Pending confirmation records are checked against their owner, not the visitor."""
    from unittest.mock import Mock

    from django.contrib.auth.models import AnonymousUser

    model = Mock()
    model.objects.select_related.return_value.filter.return_value.first.return_value = SimpleNamespace(user=locked)
    monkeypatch.setattr(recovery.apps, "get_model", lambda *_: model)
    request = rf.get("/email_confirm/token")
    request.user = AnonymousUser()
    request.resolver_match = SimpleNamespace(url_name=name)
    response = recovery.response(request, {"key": "old-token"})
    assert response.status_code == 403


def test_email_save_safeguard(rf, locked):
    """Web email changes are blocked while unrelated saves remain legal."""
    from django.contrib.auth.models import AnonymousUser
    from django.core.exceptions import PermissionDenied

    request = rf.post("/external-flow")
    request.user = AnonymousUser()
    token = current_request.set(request)
    try:
        locked.first_name = "A name"
        locked.save(update_fields=["first_name"])
        locked.email = "unauthorized@example.org"
        with pytest.raises(PermissionDenied):
            locked.save(update_fields=["email"])
    finally:
        current_request.reset(token)
    locked.refresh_from_db()
    assert locked.email == "demo@example.org"
