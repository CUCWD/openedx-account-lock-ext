"""Data-backed Teak acceptance tests; run explicitly inside the platform test environment."""

import io
from unittest.mock import patch

from common.djangoapps.student.models import CourseEnrollment, EnrollmentNotAllowed, UserProfile
from common.djangoapps.student.tests.factories import UserFactory
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.management import call_command
from django.test import override_settings
from django.utils.http import int_to_base36
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from openedx_account_lock_ext.settings.common import MIDDLEWARE


class ManagedCourseIntegration(ModuleStoreTestCase):
    """Exercise native course views, enrollment, recovery, and profile provisioning."""

    def setUp(self):
        """Create real courses and preexisting enrollments before applying the lock."""
        super().setUp()
        self.allowed = CourseFactory.create()
        self.other = CourseFactory.create()
        self.user = UserFactory.create(password="managed-integration-password")
        CourseEnrollment.enroll(self.user, self.allowed.id)
        CourseEnrollment.enroll(self.user, self.other.id)
        group, _ = Group.objects.get_or_create(name="locked_account")
        self.user.groups.add(group)
        configuration = override_settings(
            OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS=[str(self.allowed.id)],
            MIDDLEWARE=[entry for entry in settings.MIDDLEWARE if entry != MIDDLEWARE] + [MIDDLEWARE],
        )
        configuration.enable()
        self.addCleanup(configuration.disable)
        self.client.force_login(self.user)

    def test_allowed_course(self):
        """The actual Learning MFE outline endpoint retains ordinary course access."""
        response = self.client.get(f"/api/course_home/outline/{self.allowed.id}")
        self.assertEqual(response.status_code, 200)

    def test_disallowed_existing_enrollment(self):
        """A preexisting enrollment cannot bypass the native API guard."""
        response = self.client.get(f"/api/course_home/outline/{self.other.id}")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "account_locked")

    def test_native_enrollment_filter(self):
        """The platform model translates the plugin filter denial to EnrollmentNotAllowed."""
        with self.assertRaises(EnrollmentNotAllowed):
            CourseEnrollment.enroll(self.user, self.other.id)

    def test_native_password_token(self):
        """A valid platform-issued token cannot reset managed credentials after logout."""
        token = default_token_generator.make_token(self.user)
        self.client.logout()
        response = self.client.post(
            f"/password/reset/{int_to_base36(self.user.pk)}-{token}/",
            {"new_password1": "replacement-password", "new_password2": "replacement-password"},
        )
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("managed-integration-password"))

    def test_native_profile_provisioning(self):
        """The real student signals and profile model accept command-created active users."""
        with patch("sys.stdin", io.StringIO("Provisioned-demo-password-2026\n")):
            call_command(
                "create_locked_user",
                username="provisioned-demo",
                email="provisioned-demo@example.org",
                first_name="Provisioned",
                last_name="Demo",
                no_input=True,
                password_stdin=True,
            )
        profile = UserProfile.objects.get(user__username="provisioned-demo")
        self.assertEqual(profile.name, "Provisioned Demo")
        self.assertTrue(profile.user.is_active)
        self.assertTrue(profile.user.groups.filter(name="locked_account").exists())
