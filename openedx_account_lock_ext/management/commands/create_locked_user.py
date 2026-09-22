"""Create an activated managed account without granting administrative privileges."""

import getpass
import sys
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from openedx_account_lock_ext.conf import GROUP


class Command(BaseCommand):
    """Provision a new account; never update or convert an existing user."""

    help = "Create an active, nonstaff managed account in the locked_account group."

    def add_arguments(self, parser):
        """Accept identity fields and a password without command-line secret exposure."""
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--no-input", action="store_true")
        parser.add_argument("--password-stdin", action="store_true")

    def handle(self, *args, **options):
        """Validate first, then commit the user, profile, and membership atomically."""
        model, fields = self._identity(options)
        user = model(**fields)
        password = self._password(options)
        try:
            validate_password(password, user)
            user.set_password(password)
            user.full_clean()
            with transaction.atomic():
                group, _ = Group.objects.get_or_create(name=GROUP)
                # Serialize this command's duplicate-email check on databases with row locks.
                Group.objects.select_for_update().get(pk=group.pk)
                manager = model._default_manager  # pylint: disable=protected-access
                if manager.filter(**{model.USERNAME_FIELD + "__iexact": fields[model.USERNAME_FIELD]}).exists():
                    raise CommandError("An account with this username already exists; nothing was changed.")
                email_field = model.get_email_field_name()
                if manager.filter(**{email_field + "__iexact": fields[email_field]}).exists():
                    raise CommandError("An account with this email already exists; nothing was changed.")
                user._called_by_management_command = True  # pylint: disable=protected-access
                self._check_pending_enrollments(user)
                user.save()
                user.groups.add(group)
                self._ensure_profile(user, options)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        except IntegrityError as exc:
            raise CommandError("Account creation conflicted with existing data; nothing was changed.") from exc
        self.stdout.write(f"Created active locked account: {user.get_username()}")

    @staticmethod
    def _identity(options):
        model: Any = get_user_model()  # A configured model may extend AbstractBaseUser in arbitrary ways.
        field_names = {field.name for field in model._meta.fields}  # pylint: disable=protected-access
        username_field, email_field = model.USERNAME_FIELD, model.get_email_field_name()
        fields = {username_field: options["username"], email_field: options["email"]}
        if username_field == email_field and options["username"] != options["email"]:
            raise CommandError("This user model uses email as its login: --username and --email must match.")
        for field, value in (("first_name", options["first_name"]), ("last_name", options["last_name"])):
            if field in field_names:
                fields[field] = value
            elif value:
                raise CommandError(f"The configured user model does not support {field}.")
        for field in ("is_active", "is_staff", "is_superuser"):
            if field not in field_names:
                raise CommandError(f"The configured user model requires an adapter: missing writable {field}.")
        if not hasattr(model, "groups"):
            raise CommandError("The configured user model must support Django groups.")
        fields.update(is_active=True, is_staff=False, is_superuser=False)
        return model, fields

    @staticmethod
    def _password(options):
        if options["password_stdin"]:
            password = sys.stdin.readline().rstrip("\r\n")
        elif options["no_input"]:
            raise CommandError("--no-input requires --password-stdin.")
        else:
            try:
                password = getpass.getpass("Password: ")
                if password != getpass.getpass("Password (again): "):
                    raise CommandError("Passwords do not match.")
            except (EOFError, KeyboardInterrupt) as exc:
                raise CommandError("Password entry cancelled.") from exc
        if not password:
            raise CommandError("A nonempty password is required.")
        return password

    @staticmethod
    def _check_pending_enrollments(user):
        if apps.is_installed("common.djangoapps.student"):
            enrollment = apps.get_model("student", "CourseEnrollmentAllowed")
            if enrollment.objects.filter(email=user.email, auto_enroll=True).exists():
                raise CommandError("Remove pending automatic enrollments for this email before provisioning it.")

    @staticmethod
    def _ensure_profile(user, options):
        if apps.is_installed("common.djangoapps.student"):
            model = apps.get_model("student", "UserProfile")
            profile, _ = model.objects.get_or_create(user=user)
            profile.name = " ".join(part for part in (options["first_name"], options["last_name"]) if part)
            profile.save(update_fields=["name"])
