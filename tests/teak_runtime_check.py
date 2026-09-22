"""Read-only URL/adaptation smoke check inside a Teak LMS image; no database writes."""

import os


def main():
    """Load the real LMS application registry and resolve protected native callbacks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lms.envs.test")
    import django
    from django.conf import settings
    from django.urls import Resolver404, resolve

    settings.OPENEDX_ACCOUNT_LOCK_REQUIRE_MFE_GATEWAY = False
    settings.FEATURES["ENABLE_DISCUSSION_SERVICE"] = True
    django.setup()
    from openedx_account_lock_ext.adapters import guarded_callback
    from openedx_account_lock_ext.settings.common import MIDDLEWARE

    assert MIDDLEWARE in settings.MIDDLEWARE
    course = "course-v1:Demo+Allowed+2026"
    block = "block-v1:Demo+Allowed+2026+type@problem+block@one"
    paths = [
        "/api/user/v1/accounts/demo",
        "/api/user/v1/preferences/demo",
        "/api/profile_images/v1/demo/upload",
        f"/api/course_home/outline/{course}",
        f"/api/course_home/v1/progress/{course}",
        "/api/courses/v1/blocks/",
        "/api/enrollment/v1/enrollment",
        "/api/discussion/v1/threads/123/",
        f"/courses/{course}/xblock/{block}/handler/check",
        "/api/bookmarks/v1/bookmarks/",
        "/password_reset_confirm/1-token/",
        "/password/reset/1-token/",
        "/email_confirm/token",
    ]
    if settings.SETTINGS_MODULE.startswith("cms."):
        paths = [
            "/api/user/v1/accounts/demo",
            "/api/user/v1/preferences/demo",
            "/password_reset_confirm/1-token/",
            "/password/reset/1-token/",
        ]
    for path in paths:
        try:
            match = resolve(path)
        except Resolver404:
            raise AssertionError(f"Expected Teak route did not resolve: {path}") from None
        if hasattr(match.func, "cls"):
            assert callable(guarded_callback(match.func))
        print(f"RESOLVED {path}: {match.url_name}")
    print(f"Teak {settings.SETTINGS_MODULE} check passed (Django {django.get_version()}). No requests or DB writes.")


if __name__ == "__main__":
    main()
