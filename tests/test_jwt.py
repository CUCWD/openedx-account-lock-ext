"""Tests with Teak's JWT authenticator and split-cookie middleware."""

import time

import jwt
import pytest

pytestmark = pytest.mark.django_db


def token(user, settings):
    """Sign a test token; no authentication method is mocked."""
    return jwt.encode(
        {
            "username": user.username,
            "preferred_username": user.username,
            "email": user.email,
            "exp": int(time.time()) + 300,
        },
        settings.JWT_AUTH["JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def test_real_jwt_authorization(client, locked, settings):
    """Direct JWT requests without sessions are subject to course authorization."""
    encoded = token(locked, settings)
    assert (
        client.get(
            "/api/course_home/outline-jwt/course-v1:Demo+Allowed+2026", HTTP_AUTHORIZATION="JWT " + encoded
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/course_home/outline-jwt/course-v1:Other+Course+Run", HTTP_AUTHORIZATION="JWT " + encoded
        ).status_code
        == 403
    )


def test_split_cookie_gateway(client, locked, settings):
    """The MFE gateway recognizes real split JWT cookies even without a session."""
    settings.MIDDLEWARE = [
        "edx_django_utils.cache.middleware.RequestCacheMiddleware",
        *settings.MIDDLEWARE[:-1],
        "edx_rest_framework_extensions.auth.jwt.middleware.JwtAuthCookieMiddleware",
        "edx_rest_framework_extensions.auth.jwt.middleware.EnsureJWTAuthSettingsMiddleware",
        settings.MIDDLEWARE[-1],
    ]
    encoded = token(locked, settings)
    header, payload, signature = encoded.split(".")
    client.cookies["edx-jwt-cookie-header-payload"] = header + "." + payload
    client.cookies["edx-jwt-cookie-signature"] = signature
    response = client.get(
        "/api/account-lock/v1/authorize-jwt", HTTP_X_ACCOUNT_LOCK_ORIGINAL_URL="https://apps.example.org/account"
    )
    assert response.status_code == 403
    assert response.json()["error"] == "account_locked"


def test_outer_decorators_preserved(client, settings):
    """Adapting a DRF callback must not bypass decorators outside as_view()."""
    settings.OPENEDX_ACCOUNT_LOCK_RESTRICTED_API_PREFIXES = ["/api/user/v2/account/decorated"]
    assert client.post("/api/user/v2/account/decorated", {}).status_code == 405
