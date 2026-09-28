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


@pytest.mark.parametrize(
    "url,referrer,expected",
    [
        (
            "https://apps.example.org/account",
            "https://apps.example.org/welcome?from=account",
            "https://apps.example.org/welcome?from=account",
        ),
        (
            "https://apps.example.org/profile/demo",
            "http://apps.example.org:1996/learner-dashboard/",
            "http://apps.example.org:1996/learner-dashboard/",
        ),
        (
            "https://apps.example.org/account",
            "https://apps.example.org/",
            "http://apps.example.org:1996/learner-dashboard/",
        ),
        (
            "https://apps.example.org/profile/demo",
            None,
            "http://apps.example.org:1996/learner-dashboard/",
        ),
        (
            "https://apps.example.org/account",
            "https://evil.test/",
            "http://apps.example.org:1996/learner-dashboard/",
        ),
        (
            "https://apps.example.org/account",
            "https://apps.example.org/profile/demo",
            "http://apps.example.org:1996/learner-dashboard/",
        ),
        (
            "https://apps.example.org/account",
            "https://apps.example.org/api/user/v1/accounts/demo",
            "http://apps.example.org:1996/learner-dashboard/",
        ),
        (
            "https://apps.example.org/account",
            "https://apps.example.org/learning/course/course-v1:Other+Course+Run/home",
            "http://apps.example.org:1996/learner-dashboard/",
        ),
    ],
)
def test_mfe_gateway_redirects_or_falls_back(client, locked, settings, url, referrer, expected):
    """Caddy-marked MFE denials redirect to a safe referrer or the learner dashboard."""
    settings.OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = "http://apps.example.org:1996/learner-dashboard/"
    settings.OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS = [
        "https://apps.example.org",
        "http://apps.example.org:1996",
    ]
    headers = {
        "HTTP_X_ACCOUNT_LOCK_MFE_GATEWAY": "1",
        "HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL": url,
    }
    if referrer:
        headers["HTTP_REFERER"] = referrer
    response = client.get("/api/account-lock/v1/authorize", **headers)
    assert response.status_code == 302
    assert response.url == expected


@pytest.mark.parametrize("accept", ["application/json", "text/html", "*/*", ""])
def test_unmarked_mfe_denial_remains_json(client, locked, accept):
    """Direct gateway requests remain JSON-denied regardless of browser headers."""
    response = client.get(
        "/api/account-lock/v1/authorize",
        HTTP_ACCEPT=accept,
        HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL="https://apps.example.org/account",
    )
    assert response.status_code == 403
    assert response.json()["error"] == "account_locked"
    assert "Location" not in response


def test_mfe_malformed_url_remains_json(client, locked):
    """Malformed gateway input is rejected even when Caddy marks the request."""
    response = client.get(
        "/api/account-lock/v1/authorize",
        HTTP_X_ACCOUNT_LOCK_MFE_GATEWAY="1",
        HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL="https://apps.example.org/account/../profile",
    )
    assert response.status_code == 403
    assert response.json()["error"] == "account_locked"
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
