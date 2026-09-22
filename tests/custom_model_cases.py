"""Run explicitly in a separate process so Django starts with a swapped user model."""

import io
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_email_login(django_user_model):
    """The command honors USERNAME_FIELD and get_email_field_name()."""
    with patch("sys.stdin", io.StringIO("secure-demo-password\n")):
        call_command(
            "create_locked_user",
            username="demo@example.org",
            email="demo@example.org",
            no_input=True,
            password_stdin=True,
        )
    user = django_user_model.objects.get(email="demo@example.org")
    assert user.get_username() == "demo@example.org"
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert user.groups.filter(name="locked_account").exists()
    assert user.check_password("secure-demo-password")


def test_conflicting_identity(django_user_model):
    """Ambiguous username/email inputs fail without inserting an account."""
    with pytest.raises(CommandError, match="must match"):
        call_command("create_locked_user", username="demo", email="demo@example.org", no_input=True)
    assert not django_user_model.objects.exists()
