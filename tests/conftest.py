"""Shared managed-account fixtures."""

import pytest
from django.contrib.auth.models import Group


@pytest.fixture
def locked(django_user_model):
    """Create a real Django group member."""
    user = django_user_model.objects.create_user("demo", "demo@example.org", "testing-password")
    user.groups.add(Group.objects.create(name="locked_account"))
    return user


@pytest.fixture
def logged(client, locked):
    """Authenticate through Django sessions."""
    client.force_login(locked)
    return client
