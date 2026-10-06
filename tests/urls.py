"""Real Django and DRF views exercising plugin dispatch and authentication."""

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.http import require_GET
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from openedx_account_lock_ext.credentials import current_request
from openedx_account_lock_ext.views import GatewayAuthorization
from tests.auth import HeaderAuthentication


class ResourceView(ViewSet):
    """Return sensitive fields to test response redaction and native permissions."""

    authentication_classes = (HeaderAuthentication, SessionAuthentication)
    permission_classes = (AllowAny,)

    def retrieve(self, request, **kwargs):
        """Expose fixture data only when policy permits handler execution."""
        return Response(
            {
                "username": "demo",
                "name": "Demo",
                "email": "secret@example.org",
                "profile_image": {"has_image": False},
                "bio": "private",
                "kwargs": kwargs,
            }
        )

    def write(self, request, **kwargs):
        """Provide a mutation sentinel."""
        return Response({"written": True})


class JwtResourceView(ResourceView):
    """Exercise Teak's actual JWT authentication class."""

    authentication_classes = (JwtAuthentication, SessionAuthentication)


class JwtGateway(GatewayAuthorization):
    """Exercise the MFE gateway with actual JWT cookies."""

    authentication_classes = (JwtAuthentication, SessionAuthentication)


class LearnerCoursesView(ViewSet):
    """Return Teak-shaped learner-home and enrollment-list fixtures."""

    authentication_classes = (HeaderAuthentication, SessionAuthentication)
    permission_classes = (AllowAny,)

    def list(self, request):
        courses = [
            {"course": {"courseName": "Allowed"}, "courseRun": {"courseId": "course-v1:Demo+Allowed+2026"}},
            {"course": {"courseName": "Disallowed"}, "courseRun": {"courseId": "course-v1:Other+Course+2026"}},
        ]
        if request.path_info == "/api/learner_home/init":
            return Response({"courses": courses, "welcome_message": "Hello"})
        return Response([
            {"course_details": {"course_id": "course-v1:Demo+Allowed+2026"}},
            {"course_details": {"course_id": "course-v1:Other+Course+2026"}},
        ])


def page(request, **kwargs):
    """Supply an ordinary HTML route with a handler-execution sentinel."""
    return JsonResponse({"rendered": True})


def credential_change(request):
    """Exercise a web mutation outside the known account routes."""
    user = get_user_model().objects.get(username="demo")
    user.set_password("unauthorized-password")
    user.save()
    return JsonResponse({"changed": True})


def request_scope(request):
    """Prove request-local credential enforcement is active."""
    return JsonResponse({"active": current_request.get() is request})


resource = ResourceView.as_view(
    {"get": "retrieve", "post": "write", "put": "write", "patch": "write", "delete": "write"}
)
urlpatterns = [
    path("api/account-lock/v1/authorize-jwt", JwtGateway.as_view()),
    path("api/user/v2/account/decorated", require_GET(resource)),
    re_path(
        r"^api/course_home/outline-jwt/(?P<course_key_string>[^/]+)$", JwtResourceView.as_view({"get": "retrieve"})
    ),
    path("api/account-lock/v1/", include("openedx_account_lock_ext.urls")),
    re_path(r"^api/user/v1/accounts/(?P<username>[^/]+)/?$", resource, name="accounts_api"),
    re_path(r"^api/user/v1/preferences/(?P<username>[^/]+)/(?P<preference_key>[^/]+)/?$", resource),
    re_path(r"^api/user/.*$", resource),
    re_path(r"^api/course_home/outline/(?P<course_key_string>[^/]+)/?$", resource),
    re_path(r"^api/discussion/v1/threads/(?P<thread_id>[^/]+)/?$", resource),
    re_path(r"^api/discussion/v1/comments/(?P<comment_id>[^/]+)/?$", resource),
    path("api/discussion/v1/threads", resource),
    path("api/enrollment/v1/enrollment", resource),
    path("api/courses/v1/courses/", resource),
    path("password_reset/", page, name="password_reset"),
    re_path(r"^password_reset_confirm/(?P<uidb36>[^-]+)-(?P<token>[^/]+)/$", page, name="password_reset_confirm"),
    re_path(r"^password/reset/(?P<uidb36>[^-]+)-(?P<token>[^/]+)/$", resource, name="logistration_password_reset"),
    path("credentials", credential_change),
    path("scope", request_scope),
    path("admin/credentials", include(([path("", credential_change)], "admin"), namespace="admin")),
    re_path(r"^courses/(?P<course_id>[^/]+)/xblock/(?P<usage_key>[^/]+)/handler/(?P<handler>[^/]+)$", page),
    re_path(r"^courses/(?P<course_id>[^/]+)/.*$", page),
    re_path(r"^.*$", page),
]
