# Installation and administration

## Versions and installation

The inspected source checkout was `release/teak.3`, with Django 4.2.20,
`openedx-filters==2.0.1`, `edx-django-utils==7.4.0`, and `edx-drf-extensions==10.6.0`.
Use the deployment's locked dependencies rather than upgrading the platform to install this plugin.
Python 3.11+ is supported by the package; automated validation uses Python 3.12.

From this source directory, build the wheel:

```bash
python -m pip install build
python -m build
```

Install the wheel in the Python environment used by **both LMS and CMS**. Both entry points
are included: `lms.djangoapp` and `cms.djangoapp`. Open edX discovers the app and common settings
automatically; do not also append a duplicate entry to `INSTALLED_APPS`. No plugin migrations are needed.
The LMS discovers `/api/account-lock/v1/authorize` through `url_config`.

Tutor deployments should install the gateway integration from the separately maintained
[Tutor account-lock plugin repository](https://github.com/skilredi/tutor-skilredi-account-lock). This Django
distribution does not include or install that plugin. Add this Django package to the LMS and CMS
Python environments using your deployment's normal pinned package requirements, then rebuild those
images and restart the services through your existing deployment process.

Run Django system checks in both services after installation:

```bash
./manage.py lms check
./manage.py cms check
```

## Settings

All restriction settings are namespaced `OPENEDX_ACCOUNT_LOCK_`. Defaults live in `conf.py`.
Set them in your deployment settings; package edits are unnecessary.

```python
OPENEDX_ACCOUNT_LOCK_ALLOWED_COURSE_IDS = (
    "course-v1:YourOrg+Demo101+2026",
    "course-v1:YourOrg+Demo102+2026",
)
OPENEDX_ACCOUNT_LOCK_FALLBACK_URL = "/learner-dashboard"
OPENEDX_ACCOUNT_LOCK_RESTRICTED_PAGE_PATHS = (
    "/account/settings", "/account/password", "/account/email", "/profile",
)
```

One element configures one course. An empty tuple denies all managed-account course content and
enrollment. Catalogs remain browsable. IDs must be opaque course keys, not display names or course
numbers. Existing enrollments in disallowed courses do not grant access. No automatic enrollment
is performed; use normal Open edX enrollment tools after provisioning.

`OPENEDX_ACCOUNT_LOCK_RESTRICTED_API_PREFIXES` includes the requested six prefixes plus
`/api/profile_images/` and `/api/change_email_settings`. Replacing this setting replaces the whole
list: preserve existing entries when adding another endpoint. Matching includes an exact slashless
root and slash-delimited descendants; `/accounts-extra` is not `/accounts`.

Writes are denied regardless of method name except safe OPTIONS requests. GET/HEAD are denied
except the authenticated user's exact `/api/user/v1/accounts/{username}` bootstrap response,
redacted to `OPENEDX_ACCOUNT_LOCK_BOOTSTRAP_FIELDS` (`username`, `name`, `profile_image`), and exact
individual preference reads configured by `OPENEDX_ACCOUNT_LOCK_READ_PREFERENCE_KEYS`
(`pref-lang`, `time_zone`). Do not add email, biography, birth date, or other sensitive fields merely
to make an account/profile screen usable. Login, logout, CSRF setup, and token refresh remain native.

## Middleware ordering

`openedx_account_lock_ext.middleware.AccountLockMiddleware` must be **last** in `MIDDLEWARE`.
Plugin settings append it automatically. If another plugin later adds middleware, move the guard
back to the end in final deployment settings:

```python
guard = "openedx_account_lock_ext.middleware.AccountLockMiddleware"
MIDDLEWARE = [entry for entry in MIDDLEWARE if entry != guard] + [guard]
```

This follows `SafeSessionMiddleware`, `CacheBackedAuthenticationMiddleware`, `MessageMiddleware`,
CSRF/CORS middleware, and both `JwtAuthCookieMiddleware` and `EnsureJWTAuthSettingsMiddleware`.
The last position is required because the DRF adapter returns a dispatched response from
`process_view`: placing it earlier could skip native view middleware. Teak's course
`RedirectMiddleware` handles exceptions, not `process_view`, so the plugin still denies access
before course views can render or redirect. This is an intentional refinement of the initial plan.
The middleware is synchronous; Django adapts it for ASGI without leaking request context.

## MFE gateway

An external gateway can authorize account, profile, and learning MFE requests through the LMS
endpoint `/api/account-lock/v1/authorize`. Configure the gateway to send the exact original URL in
`X-Account-Lock-Original-Url`, forward the user's authentication cookies or Authorization header,
and set `X-Account-Lock-MFE-Gateway: 1` on its authorization subrequest. The endpoint validates the
URL against `OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS`, returns 204 for allowed requests, and returns a JSON
403 for blocked direct/API requests. Marked gateway denials redirect to a safe referring page or the
configured fallback. The endpoint does not trust client-supplied identity headers.

Configure exact public MFE origins, including development ports; do not use wildcards. The gateway
must preserve the browser's `Referer` header and route all public account/profile MFE entry paths
through authorization. A directly accessed webpack server bypasses the gateway. Tutor deployments
can use the separately maintained [Tutor account-lock plugin](https://github.com/skilredi/tutor-skilredi-account-lock)
for its gateway configuration.

## Creating and administering users

Interactive provisioning inside LMS:

```bash
./manage.py lms create_locked_user --username demo --email demo@example.org \
  --first-name Demo --last-name Learner
```

Noninteractive provisioning:

```bash
your-secret-manager-read-command | ./manage.py lms create_locked_user \
  --username demo --email demo@example.org --no-input --password-stdin
```

Stdin supplies one password line. Do not put a literal secret in shell history or enable shell
tracing. Django's password validators apply. Duplicate username/email inputs (case-insensitive)
fail without changing existing users. Creation, profile provisioning, and group assignment are
atomic. The account starts active, nonstaff, and nonsuperuser. Pending platform auto-enrollments
for the email must be removed first; the command rejects them rather than silently enrolling.

The command supports swappable user models with Django groups, password APIs, writable privilege
flags, and configured username/email fields. Email-login models require matching `--username`
and `--email`. Unsupported mandatory custom fields produce validation errors, not partially
created users. This does not imply that edx-platform itself supports every custom user model.

Use Django admin to add/remove `locked_account` membership, or use an authorized management shell:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

user = get_user_model().objects.get(username="existing-demo")
group, _ = Group.objects.get_or_create(name="locked_account")
user.groups.add(group)       # apply restrictions on the next request
# user.groups.remove(group)  # remove restrictions on the next request
```

Membership is cached only during a request. Staff/superusers bypass restrictions even if in the
group; do not grant those flags to demo users. Administrators can use Django admin's permitted
password/email controls or `./manage.py lms changepassword demo`. Some Teak deployments disable
admin password views; use the command in that case. Changing email through a management shell
must use `user.save()` so platform signals run. Follow normal platform procedures to invalidate
old sessions/tokens after administrator credential changes.
