"""MFE authorization via a real authenticated DRF endpoint."""

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "url,status",
    [
        ("https://apps.example.org/account", 403),
        ("https://apps.example.org/profile/demo", 403),
        ("https://apps.example.org/learning/course/course-v1:Demo+Allowed+2026/home", 204),
        ("https://apps.example.org/learning/course/course-v1:Other+Course+Run/home", 403),
        ("https://evil.test/account", 403),
        ("http://apps.example.org/account", 403),
        ("https://apps.example.org@evil.test/account", 403),
        ("https://apps.example.org/%61ccount", 403),
        ("https://apps.example.org/learning/course", 403),
        ("https://apps.example.org/account/../profile", 403),
        ("https://apps.example.org//account", 403),
        ("https://apps.example.org/ACCOUNT", 403),
        ("", 403),
    ],
)
def test_mfe_entry(client, locked, url, status):
    """Gateway validates origins and course/account policy before serving an MFE."""
    response = client.get(
        "/api/account-lock/v1/authorize", HTTP_AUTHORIZATION="Bearer demo", HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL=url
    )
    assert response.status_code == status
    assert response["Cache-Control"] == "no-store, private"
    assert "Location" not in response


def test_anonymous_and_staff(client, locked):
    """Nonlocked gateway requests continue to native MFE authentication."""
    url = "https://apps.example.org/account"
    assert client.get("/api/account-lock/v1/authorize", HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL=url).status_code == 204
    locked.is_staff = True
    locked.save()
    assert (
        client.get(
            "/api/account-lock/v1/authorize", HTTP_AUTHORIZATION="Bearer demo", HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL=url
        ).status_code
        == 204
    )
