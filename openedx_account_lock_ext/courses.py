"""Course ownership resolution for Teak request surfaces."""

import json
import re
from collections.abc import Mapping

from django.utils.module_loading import import_string
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import AssetKey, CourseKey, UsageKey

from . import conf

COURSE_FIELDS = ("course_id", "course_key", "course_key_string", "courseId", "course")
USAGE_FIELDS = ("usage_key", "usage_id", "block_id", "block_key", "usage_key_string")
CATALOG_PATHS = (
    "/api/courses/v1/courses",
    "/api/courses/v2/courses",
    "/api/courses/v1/course_ids",
    "/courses",
    "/api/learner_home/init",
    "/api/enrollment/v1/enrollment",
)
# Only these endpoints actually select their resource using a submitted course/usage key.
# Adding ?course_id=allowed to an arbitrary object endpoint must NEVER authorize it.
INPUT_COURSE_PATHS = (
    "/change_enrollment",
    "/api/enrollment/v1/enrollment",
    "/api/enrollment/v1/unenroll",
    "/api/courses/v1/blocks",
    "/api/courses/v2/blocks",
    "/api/bookmarks/v1/bookmarks",
    "/api/course_home/save_course_goal",
    "/api/course_home/dismiss_welcome_message",
    "/api/course_home/v1/save_course_goal",
    "/api/course_home/v1/dismiss_welcome_message",
    "/api/discussion/v1/threads",
    "/api/discussion/v1/comments",
    "/api/keyterms/v1/course_terms",
)


class UnresolvedCourse(ValueError):
    """A protected resource cannot be unambiguously assigned to a course."""


def canonical(value):
    """Canonicalize an opaque course key without conflating branches or course runs."""
    try:
        return str(CourseKey.from_string(str(value)))
    except (InvalidKeyError, TypeError, ValueError) as exc:
        raise UnresolvedCourse("Invalid course identifier") from exc


def allowed(value):
    """Check membership; an empty configuration grants no course access."""
    try:
        return canonical(value) in {canonical(item) for item in conf.get("ALLOWED_COURSE_IDS")}
    except UnresolvedCourse:
        return False


def usage_course(value):
    """Resolve the owning course embedded in a course-backed usage key."""
    try:
        key = value if isinstance(value, UsageKey) else UsageKey.from_string(str(value))
        return canonical(key.course_key)
    except (InvalidKeyError, AttributeError, TypeError, ValueError) as exc:
        raise UnresolvedCourse("Invalid or non-course usage key") from exc


def protected(request, kwargs):
    """Identify course surfaces, including identifiers outside the URL path."""
    path = conf.normalized(request.path_info)
    if path in CATALOG_PATHS and request.method in {"GET", "HEAD", "OPTIONS"}:
        return False
    if any(name in kwargs for name in COURSE_FIELDS + USAGE_FIELDS):
        return True
    return (
        conf.matches_any(path, conf.get("COURSE_API_PREFIXES"))
        or conf.matches_any(
            path, ("/courses", "/learning/course", "/xblock", "/xblocks", "/change_enrollment", "/api/courses")
        )
        or path.startswith(("/asset-v1:", "/c4x/", "/assets/courseware/"))
        or bool(re.match(r"^/api/mobile/[^/]+/(course_info|users/[^/]+/course_enrollments)", path))
    )


def _values(data, field):
    if hasattr(data, "getlist"):
        return data.getlist(field)
    value = data.get(field)
    return value if isinstance(value, (list, tuple)) else [value]


def _collect(data, keys):
    if not isinstance(data, Mapping):
        return
    for field in COURSE_FIELDS + USAGE_FIELDS:
        if field not in data:
            continue
        for value in _values(data, field):
            if isinstance(value, Mapping):
                value = value.get("id") or value.get("course_id")
            if value is not None:
                keys.add(usage_course(value) if field in USAGE_FIELDS else canonical(value))
    # Teak enrollment API accepts {"course_details": {"course_id": ...}}.
    if "course_details" in data:
        _collect(data["course_details"], keys)


def discussion_owner(kind, identifier):
    """Look up forum ownership server-side; never trust a supplied course_id."""
    comment_class = import_string("openedx.core.djangoapps.django_comment_common.comment_client.comment.Comment")
    thread_class = import_string("openedx.core.djangoapps.django_comment_common.comment_client.thread.Thread")

    try:
        resource = (thread_class if kind == "thread" else comment_class)(id=identifier).retrieve()
        if kind == "comment":
            resource = thread_class(id=resource.thread_id).retrieve()
        return canonical(resource.course_id)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # The forum may be unavailable. Never turn lookup failure into authorization.
        raise UnresolvedCourse("Cannot resolve discussion ownership") from exc


def _asset_course(path):
    # Teak prefixes the original asset key with /assets/courseware/[vN/]digest.
    if path.startswith("/assets/courseware/"):
        path = re.sub(r"^/assets/courseware/(v[\d]/)?[a-f0-9]{32}", "", path)
    if path.startswith("/asset-v1:"):
        try:
            key = path.lstrip("/").replace("block/", "block@", 1)
            return canonical(AssetKey.from_string(key).course_key)
        except (InvalidKeyError, ValueError) as exc:
            raise UnresolvedCourse("Invalid asset key") from exc
    # Legacy c4x URLs omit the run; malformed versioned URLs cannot establish ownership.
    if path.startswith(("/c4x/", "/assets/courseware/")):
        raise UnresolvedCourse("Asset URL does not identify its course run")
    return None


def resolve(request, kwargs):
    """Resolve every supplied course identifier and require consistent ownership."""
    # Each branch corresponds to an independently verified Teak transport for course identity.
    # pylint: disable=too-many-branches
    keys: set[str] = set()
    authoritative: set[str] = set()
    _collect(kwargs, authoritative)
    data = getattr(request, "data", None)
    if data is None:
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body)
            except (ValueError, UnicodeDecodeError) as exc:
                raise UnresolvedCourse("Invalid request body") from exc
        else:
            data = request.POST
    for source in (kwargs, request.GET, data):
        _collect(source, keys)
    path = request.path_info
    if conf.normalized(path) in INPUT_COURSE_PATHS:
        for source in (request.GET, data):
            _collect(source, authoritative)
            if isinstance(source, Mapping) and "course_number" in source:
                mapped = conf.get("COURSE_NUMBER_MAP").get(source["course_number"])
                if not mapped:
                    raise UnresolvedCourse("Course number has no configured course-run mapping")
                authoritative.add(canonical(mapped))
    asset_course = _asset_course(path)
    if asset_course:
        authoritative.add(asset_course)
    # URL resolver kwargs are authoritative; this also supports the MFE gateway.
    if not keys:
        match = re.match(r"^/(?:courses|learning/course)/(course-v1:[^/]+)(?:/|$)", path)
        if match:
            authoritative.add(canonical(match[1]))
    if "/discussion" in path:
        for source in (kwargs, request.GET, data):
            for field, kind in (("thread_id", "thread"), ("comment_id", "comment"), ("parent_id", "comment")):
                if isinstance(source, Mapping) and source.get(field):
                    authoritative.add(discussion_owner(kind, source[field]))
    for dotted_path in conf.get("COURSE_RESOLVERS"):
        result = import_string(dotted_path)(request, kwargs)
        if result is not None:
            authoritative.add(canonical(result))
    keys.update(authoritative)
    if not authoritative or len(keys) != 1:
        raise UnresolvedCourse("Missing or conflicting course ownership")
    return keys.pop()


def denied(request, kwargs):
    """Deny unresolved/disallowed course requests; do not grant underlying access."""
    if not protected(request, kwargs):
        return False
    try:
        return not allowed(resolve(request, kwargs))
    except UnresolvedCourse:
        return True
