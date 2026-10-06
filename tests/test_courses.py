"""Course authorization across URL, query, body, block and forum ownership."""

import pytest

from openedx_account_lock_ext import courses

pytestmark = pytest.mark.django_db
ALLOWED = "course-v1:Demo+Allowed+2026"
OTHER = "course-v1:Other+Course+2026"


@pytest.mark.parametrize("course,status", [(ALLOWED, 200), (OTHER, 302)])
def test_direct_course(logged, course, status):
    """Direct navigation cannot bypass the allowlist."""
    assert logged.get(f"/courses/{course}/courseware").status_code == status


def test_multi_and_empty(logged, settings):
    """Both multi-course and fail-closed empty configurations are supported."""
    settings.OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = [ALLOWED, OTHER]
    assert logged.get(f"/courses/{OTHER}/courseware").status_code == 200
    settings.OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = []
    assert logged.get(f"/courses/{ALLOWED}/courseware").status_code == 302
    assert logged.get("/api/courses/v1/courses/").status_code == 200


@pytest.mark.parametrize("course,status", [(ALLOWED, 200), (OTHER, 403)])
def test_course_api_bearer(client, locked, course, status):
    """Course API auth occurs before the managed-course decision."""
    response = client.get(f"/api/course_home/outline/{course}", HTTP_AUTHORIZATION="Bearer demo")
    assert response.status_code == status


def test_enrollment_payload(logged):
    """Enrollment courses embedded in JSON are enforced."""
    for course, status in [(ALLOWED, 200), (OTHER, 403)]:
        response = logged.post(
            "/api/enrollment/v1/enrollment", {"course_details": {"course_id": course}}, content_type="application/json"
        )
        assert response.status_code == status


@pytest.mark.parametrize(
    "path,collection",
    [("/api/learner_home/init", "courses"), ("/api/enrollment/v1/enrollment", None)],
)
def test_locked_dashboard_hides_disallowed_enrollments(logged, path, collection):
    response = logged.get(path)
    assert response.status_code == 200
    data = response.json()
    entries = data[collection] if collection else data
    assert len(entries) == 1
    if collection:
        assert entries[0]["courseRun"]["courseId"] == ALLOWED
    else:
        assert entries[0]["course_details"]["course_id"] == ALLOWED


def test_locked_dashboard_empty_allowlist_hides_all_courses(logged, settings):
    settings.OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = []
    assert logged.get("/api/learner_home/init").json()["courses"] == []
    assert logged.get("/api/enrollment/v1/enrollment").json() == []


def test_locked_dashboard_tracks_allowlist_changes(logged, settings):
    settings.OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = [OTHER]
    response = logged.get("/api/learner_home/init")
    assert [item["courseRun"]["courseId"] for item in response.json()["courses"]] == [OTHER]
    response = logged.get("/api/enrollment/v1/enrollment")
    assert [item["course_details"]["course_id"] for item in response.json()] == [OTHER]


def test_unlocked_dashboard_keeps_all_enrollments(client, django_user_model):
    user = django_user_model.objects.create_user("unlocked", password="testing-password")
    client.force_login(user)
    response = client.get("/api/learner_home/init")
    assert response.status_code == 200
    assert len(response.json()["courses"]) == 2


def test_conflicting_query(logged):
    """Neither URL/body conflicts nor duplicate query parameters can authorize a resource."""
    assert logged.get(f"/api/course_home/outline/{ALLOWED}?course_id={OTHER}").status_code == 403
    assert logged.get(f"/api/course_home/outline/{ALLOWED}?course_id={ALLOWED}&course_id={OTHER}").status_code == 403


def test_usage_ownership(logged):
    """XBlock usage keys must agree with the URL's course."""
    good = "block-v1:Demo+Allowed+2026+type@problem+block@one"
    bad = "block-v1:Other+Course+2026+type@problem+block@one"
    assert logged.post(f"/courses/{ALLOWED}/xblock/{good}/handler/check", {}).status_code == 200
    assert logged.post(f"/courses/{ALLOWED}/xblock/{bad}/handler/check", {}).status_code == 403


@pytest.mark.parametrize("kind", ["threads", "comments"])
def test_forum_resource_ownership(logged, monkeypatch, kind):
    """Supplying an allowed course cannot disguise a forbidden thread/comment."""
    monkeypatch.setattr(courses, "discussion_owner", lambda *_: OTHER)
    assert logged.get(f"/api/discussion/v1/{kind}/123?course_id={ALLOWED}").status_code == 403
    monkeypatch.setattr(courses, "discussion_owner", lambda *_: ALLOWED)
    assert logged.get(f"/api/discussion/v1/{kind}/123").status_code == 200


def test_forum_lookup_failure(logged, monkeypatch):
    """Unavailable ownership never becomes an allow decision."""

    def failure(*args):
        raise courses.UnresolvedCourse("offline")

    monkeypatch.setattr(courses, "discussion_owner", failure)
    assert logged.get("/api/discussion/v1/threads/123").status_code == 403


def test_enrollment_filter(locked):
    """Exercise the actual installed Open edX filter pipeline."""
    from opaque_keys.edx.keys import CourseKey
    from openedx_filters.learning.filters import CourseEnrollmentStarted

    with pytest.raises(CourseEnrollmentStarted.PreventEnrollment):
        CourseEnrollmentStarted.run_filter(user=locked, course_key=CourseKey.from_string(OTHER), mode="audit")
    result = CourseEnrollmentStarted.run_filter(user=locked, course_key=CourseKey.from_string(ALLOWED), mode="audit")
    assert result == (locked, CourseKey.from_string(ALLOWED), "audit")


@pytest.mark.parametrize(
    "path,kwargs",
    [
        ("/api/course_home/progress/anything", {}),
        ("/api/courses/v1/blocks", {}),
        ("/api/mobile/v1/course_info/x", {}),
        ("/api/bookmarks/v1/bookmarks", {}),
        ("/xblock/key", {"usage_key": "bad"}),
        ("/asset-v1:Demo+Allowed+2026+type@asset+block@image.png", {}),
        ("/c4x/Demo/Allowed/asset/image.png", {}),
        ("/assets/courseware/hash/image.png", {}),
        ("/api/progress/x", {}),
        ("/custom/course", {"course_key": OTHER}),
    ],
)
def test_route_inventory(rf, path, kwargs):
    """Documented route families enter ownership enforcement."""
    assert courses.protected(rf.get(path), kwargs)


def test_asset_key_and_invalid_configuration(rf, settings):
    """Course-backed assets retain access; invalid IDs never broaden access."""
    request = rf.get("/asset-v1:Demo+Allowed+2026+type@asset+block@image.png")
    assert not courses.denied(request, {})
    settings.OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = ["invalid"]
    assert courses.denied(request, {})


def test_forged_course_selector(rf):
    """A course query parameter cannot authorize an unknown server-owned object."""
    request = rf.get("/api/edx_proctoring/attempt/123", {"course_id": ALLOWED})
    assert courses.denied(request, {})


def test_versioned_asset(rf):
    """Teak's hashed asset prefix does not hide the embedded course key."""
    asset = "/asset-v1:Demo+Allowed+2026+type@asset+block/image.png"
    path = "/assets/courseware/v1/" + "a" * 32 + asset
    assert not courses.denied(rf.get(path), {})


def test_keyterms_mapping(rf, settings):
    """Existing course-number APIs require explicit run ownership."""
    request = rf.get("/api/keyterms/v1/course_terms/", {"course_number": "DEMO101"})
    assert courses.denied(request, {})
    settings.OPENEDX_ACCOUNT_LOCK_COURSE_NUMBER_MAP = {"DEMO101": ALLOWED}
    assert not courses.denied(request, {})
    assert courses.denied(rf.get("/api/keyterms/v1/glossary/", {"course_id": ALLOWED}), {})
