"""Use Teak's enrollment hook in addition to HTTP course authorization."""

from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted

from .courses import allowed
from .identity import is_locked


class AllowlistedEnrollment(PipelineStep):
    """Prevent managed accounts from acquiring disallowed enrollments."""

    def run_filter(self, **kwargs):
        """Retain all existing Open edX enrollment checks after this additional denial."""
        if is_locked(kwargs["user"]) and not allowed(kwargs["course_key"]):
            raise CourseEnrollmentStarted.PreventEnrollment("This account cannot enroll in this course.")
        return kwargs
