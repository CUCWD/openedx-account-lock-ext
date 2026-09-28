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

For Tutor, install the source and optional Tutor dependencies in the Tutor host environment:

```bash
python -m pip install -e '.[tutor]'
tutor plugins enable account-lock
```

That enables settings and gateway patches; **it does not install Python packages in the LMS image**.
Publish your wheel to your package index or commit the source to your own repository, then add its
pinned requirement to Tutor's existing `OPENEDX_EXTRA_PIP_REQUIREMENTS` list. Preserve other entries.
A source requirement can be `git+https://YOUR-REPOSITORY/openedx-account-lock-ext.git@PINNED-COMMIT`.
No public package index release is assumed. Rebuild the `openedx` and `mfe` images and restart
LMS, CMS, and MFE services through your existing deployment process. This implementation does not
change the running deployment automatically.

Check effective configuration in **both services** after rebuilding:

```bash
tutor local run lms ./manage.py lms check
tutor local run cms ./manage.py cms check
```

For a mounted development checkout, install it inside the container's Python environment as well;
a host-side editable install does not make it available to containers.

## Settings

All restriction settings are namespaced `OPENEDX_ACCOUNT_LOCK_`. Defaults live in `conf.py`.
Set them in your deployment settings/Tutor settings patch; package edits are unnecessary.

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

The Tutor account-lock plugin owns `ACCOUNT_LOCK_ALLOWED_COURSE_IDS` and
`ACCOUNT_LOCK_FALLBACK_URL`, rendering the equivalent Django settings in LMS and CMS. Keep
account-lock settings out of unrelated Tutor plugins so a later patch cannot overwrite the
allowlist. The default local course is `course-v1:diffOrg+DemoX+summer_2026`, and the fallback is
`/learner-dashboard`.

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

The Tutor patch adds Caddy `forward_auth` for `/account`, `/profile`, and `/learning/course`
and their descendants. It authenticates against the LMS endpoint using existing cookies or the
Authorization header. Caddy overwrites the original-URL header; no asserted user-ID header is trusted.
The endpoint validates the original URL against `OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS`, returns 204
for an allowed request, and returns JSON 403 for direct/API requests. Caddy marks its MFE
authorization subrequest with `X-Account-Lock-MFE-Gateway: 1`; blocked MFE entries receive a safe
302 to their referring page, or to `/learner-dashboard` when the referrer is missing or unsafe.
Responses are private and uncached.

Production origins are derived from `ENABLE_HTTPS` and `MFE_HOST`. The configured external scheme
is used even when the proxy-to-Caddy hop is HTTP. Ensure auth cookies actually reach the MFE host
and are forwarded to LMS. Independent browser origins must use the deployment's normal Open edX
cookie configuration; do not solve cookie issues by trusting client-supplied identity headers.

Webpack development servers bypass the production MFE Caddy server. Put the development server
behind the same gateway (proxy its allowed requests onward to the webpack port), or treat that
server as unprotected. Add exact origins with ports, for example
`http://apps.local.openedx.io:1997`, to `OPENEDX_ACCOUNT_LOCK_MFE_ORIGINS`; never use wildcards.
Simply setting `MFE_GATEWAY_ENABLED=True` does not install a development reverse proxy, and
opening the webpack server directly cannot exercise the redirect behavior.

Without Tutor, install equivalent gateway rules and configure `MFE_ORIGINS` and
`MFE_GATEWAY_ENABLED=True`. `REQUIRE_MFE_GATEWAY=False` is only for installations that do not serve
independent account/profile MFEs; it does not make a Django-only deployment protect static MFEs.

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
