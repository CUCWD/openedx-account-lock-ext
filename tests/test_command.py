"""Provisioning validation, activation, duplicate protection, and atomicity."""

import io
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def create(**kwargs):
    """Invoke the script-safe CLI with a password on stdin."""
    with patch("sys.stdin", io.StringIO("strong-password-2026\n")):
        call_command(
            "create_locked_user",
            username="demo",
            email="demo@example.org",
            no_input=True,
            password_stdin=True,
            stdout=io.StringIO(),
            **kwargs,
        )


def test_create(django_user_model):
    """Provisioning activates the account, hashes its password, and assigns the group."""
    create(first_name="Demo", last_name="Learner")
    user = django_user_model.objects.get(username="demo")
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert user.first_name == "Demo" and user.last_name == "Learner"
    assert user.check_password("strong-password-2026")
    assert user.groups.filter(name="locked_account").exists()


@pytest.mark.parametrize(
    "identity",
    [
        {"username": "demo", "email": "old@example.org"},
        {"username": "existing", "email": "DEMO@example.org"},
        {"username": "DEMO", "email": "old@example.org"},
    ],
)
def test_duplicates(django_user_model, identity):
    """Existing usernames and email variants never convert or modify an account."""
    user = django_user_model.objects.create_user(password="old-password", **identity)
    with pytest.raises(CommandError):
        create()
    user.refresh_from_db()
    assert user.check_password("old-password")
    assert not user.groups.exists()
    assert django_user_model.objects.count() == 1


def test_noninteractive_requires_secret(django_user_model):
    """Deployment scripts cannot accidentally create passwordless accounts."""
    with pytest.raises(CommandError, match="password-stdin"):
        call_command("create_locked_user", username="demo", email="demo@example.org", no_input=True)
    assert not django_user_model.objects.exists()


@pytest.mark.parametrize("password", ["", "short\n"])
def test_password_validation(password, django_user_model):
    """Reject empty and validator-disallowed passwords."""
    with patch("sys.stdin", io.StringIO(password)), pytest.raises(CommandError):
        call_command(
            "create_locked_user", username="demo", email="demo@example.org", no_input=True, password_stdin=True
        )
    assert not django_user_model.objects.exists()


def test_interactive(django_user_model):
    """Interactive entry confirms passwords without accepting a CLI secret option."""
    with patch("getpass.getpass", side_effect=["password-one", "password-two"]), pytest.raises(CommandError):
        call_command("create_locked_user", username="demo", email="demo@example.org")
    assert not django_user_model.objects.exists()


def test_rollback(django_user_model):
    """A late failure cannot leave a user without restrictions."""
    with (
        patch(
            "openedx_account_lock_ext.management.commands.create_locked_user.Command._ensure_profile",
            side_effect=CommandError("profile failure"),
        ),
        pytest.raises(CommandError),
    ):
        create()
    assert not django_user_model.objects.exists()
    assert not Group.objects.exists()
