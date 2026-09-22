"""Test-only per-view authentication."""

from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class HeaderAuthentication(BaseAuthentication):
    """Model a per-view bearer authenticator that runs after Django middleware."""

    def authenticate(self, request):
        """Resolve a test bearer identity, rejecting malformed credentials."""
        header = request.headers.get("Authorization")
        if not header:
            return None
        try:
            return get_user_model().objects.get(username=header.removeprefix("Bearer ")), None
        except get_user_model().DoesNotExist as exc:
            raise AuthenticationFailed("Invalid token") from exc

    def authenticate_header(self, request):
        """Preserve DRF authentication errors as 401 responses."""
        return "Bearer"
