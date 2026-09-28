"""End-to-end request policy tests using Django and DRF dispatch."""

import pytest
from django.contrib.messages import get_messages

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "path",
    [
        "/account/settings",
        "/account/settings/",
        "/account/settings/nested",
        "/account/password",
        "/account/email/",
        "/profile",
        "/profile/demo",
        "/profile/demo/",
    ],
)
def test_restricted_pages(logged, path):
    """Protected HTML pages never reach their view."""
    response = logged.get(path)
    assert response.status_code == 302
    assert response.url == "/learner-dashboard"
    assert [str(message) for message in get_messages(response.wsgi_request)] == [
        "This page is restricted for managed accounts.",
    ]


@pytest.mark.parametrize("path", ["/dashboard", "/profiled", "/account/settings-help", "/account/finish_auth"])
def test_unrelated_pages(logged, path):
    """Boundary matching does not restrict similarly named paths."""
    assert logged.get(path).status_code == 200


@pytest.mark.parametrize("kind", ["anonymous", "regular", "staff", "superuser", "removed"])
def test_bypass(client, locked, django_user_model, kind):
    """Only authenticated, nonprivileged group members are restricted."""
    if kind == "regular":
        locked = django_user_model.objects.create_user("regular")
    elif kind == "staff":
        locked.is_staff = True
        locked.save()
    elif kind == "superuser":
        locked.is_superuser = True
        locked.save()
    elif kind == "removed":
        locked.groups.clear()
    if kind != "anonymous":
        client.force_login(locked)
    assert client.get("/profile/demo").status_code == 200
    assert client.patch("/api/user/v1/accounts/demo", {}, content_type="application/json").status_code == 200
    assert client.get("/courses/course-v1:Other+Course+Run/courseware").status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize(
    "path",
    [
        "/api/user/v1/accounts",
        "/api/user/v1/accounts/demo",
        "/api/user/v1/preferences/demo",
        "/api/user/v2/account/password",
        "/api/user/v2/account/email/nested",
        "/api/user/v2/account/name/",
        "/api/user/v2/account/profile",
    ],
)
def test_api_writes(logged, method, path):
    """Every unsafe method is denied using stable JSON, never redirected."""
    response = getattr(logged, method)(path, {}, content_type="application/json")
    assert response.status_code == 403
    assert response.json() == {"error": "account_locked", "detail": "This account cannot access this resource."}
    assert "Location" not in response


@pytest.mark.parametrize(
    "path",
    [
        "/api/user/v1/accounts/another",
        "/api/user/v1/accounts",
        "/api/user/v1/preferences/demo",
        "/api/user/v2/account/profile",
        "/api/user/v1/preferences/demo/private",
    ],
)
def test_sensitive_reads(logged, path):
    """Read-only methods do not expose account/profile data."""
    assert logged.get(path).status_code == 403
    assert logged.head(path).status_code == 403


def test_bootstrap(logged):
    """Current-user hydration retains only explicitly permitted fields."""
    response = logged.get("/api/user/v1/accounts/demo")
    assert response.json() == {"username": "demo", "name": "Demo", "profile_image": {"has_image": False}}
    assert response["Cache-Control"] == "no-store, private"


@pytest.mark.parametrize("key", ["pref-lang", "time_zone"])
def test_preference_read(logged, key):
    """Localization preference reads remain usable."""
    assert logged.get(f"/api/user/v1/preferences/demo/{key}").status_code == 200


def test_api_collision_and_options(logged):
    """Sibling prefixes remain accessible and OPTIONS performs no mutation."""
    assert logged.post("/api/user/v1/accounts-extra", {}).status_code == 200
    assert logged.options("/api/user/v1/accounts/demo").status_code == 200


def test_bearer_without_session(client, locked):
    """Per-view authentication cannot bypass middleware with an anonymous Django user."""
    response = client.patch(
        "/api/user/v1/accounts/demo", {}, content_type="application/json", HTTP_AUTHORIZATION="Bearer demo"
    )
    assert response.status_code == 403
    assert response.json()["error"] == "account_locked"
    assert client.get("/api/user/v1/accounts/demo", HTTP_AUTHORIZATION="Bearer invalid").status_code == 401


@pytest.mark.parametrize(
    "referrer,expected",
    [
        ("http://testserver/welcome?x=1", "http://testserver/welcome?x=1"),
        ("/welcome", "/welcome"),
        (None, "/learner-dashboard"),
        ("https://evil.test/", "/learner-dashboard"),
        ("//evil.test/", "/learner-dashboard"),
        ("javascript:alert(1)", "/learner-dashboard"),
        ("http://testserver@evil.test/", "/learner-dashboard"),
        ("/profile/demo", "/learner-dashboard"),
        ("/account/settings", "/learner-dashboard"),
        ("/courses/course-v1:Other+X+Run/courseware", "/learner-dashboard"),
        ("/learning/course/course-v1:Other+X+Run/home", "/learner-dashboard"),
        ("/account", "/learner-dashboard"),
        ("\\\\evil.test", "/learner-dashboard"),
    ],
)
def test_referrers(logged, referrer, expected):
    """Referrers must be safe and must not lead to another blocked page."""
    headers = {"HTTP_REFERER": referrer} if referrer else {}
    assert logged.get("/account/settings", **headers).url == expected


def test_https_and_fallback(logged, settings):
    """Reject HTTPS downgrades and validate the configured fallback at runtime."""
    settings.OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = "/welcome"
    assert logged.get("/profile", secure=True, HTTP_REFERER="http://testserver/old").url == "/welcome"
    settings.OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = "https://evil.test"
    assert logged.get("/profile").url == "/learner-dashboard"


def test_group_cache_per_request(logged, locked, django_assert_num_queries, rf):
    """Group membership is checked once per request and refreshed on the next."""
    from openedx_account_lock_ext.identity import is_locked

    request = rf.get("/")
    with django_assert_num_queries(1):
        assert is_locked(locked, request)
        assert is_locked(locked, request)
    locked.groups.clear()
    assert logged.get("/profile").status_code == 200
