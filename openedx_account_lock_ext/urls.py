"""LMS URLs exposed through Open edX plugin discovery."""

from django.urls import path

from .views import GatewayAuthorization

urlpatterns = [path("authorize", GatewayAuthorization.as_view(), name="authorize")]
