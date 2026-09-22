# Validation and release acceptance

Verified on 2026-09-17: **141 standalone tests passed**, **2 custom-user-model tests passed**,
and standalone plugin statement coverage was **90%**. The complete tox quality environment passed
(pylint 10/10, pycodestyle, pydocstyle, isort, mypy), as did Django checks. Native LMS and CMS URL/
callback checks and Caddy configuration validation passed. Wheel and source builds passed Twine
metadata validation. These results do not include the data-backed acceptance suite below.

## Automated checks

The standalone suite uses real Django/DRF request dispatch, SQLite-backed users/groups, Open edX's
installed enrollment filter, and Teak's actual `JwtAuthentication` and split-cookie middleware.
Forum ownership and pending-email records are isolated with test doubles where a running platform
service/model is unavailable. Custom email-login user tests run in a separate Django process.

Commands used from the source workspace, using a temporary Python 3.12 environment:

```bash
VIRTUALENV_OVERRIDE_APP_DATA=/private/tmp/account-lock-virtualenv \
  /private/tmp/account-lock-venv/bin/python -m tox \
  -e py312-django42,custom-user,quality --workdir /private/tmp/account-lock-tox-verified

/private/tmp/account-lock-venv/bin/python -m mypy openedx_account_lock_ext
/private/tmp/account-lock-venv/bin/python -m build
/private/tmp/account-lock-venv/bin/python -m twine check dist/*
```

Tox runs Django system checks, pytest, pylint, pycodestyle, pydocstyle, isort checks, and mypy.
The test environment disables telemetry; it does not mock JWT signature validation/authentication.
Provisioning tests also cover rollback after a late failure, duplicate case variants, password
validation, and immediate activation. Security regression tests cover forged course selectors,
foreign XBlock/discussion ownership, encoded gateway URLs, and preservation of outer view decorators.

Initial sandbox-only dependency installations could not reach PyPI; retries used authorized network
access and isolated temporary environments. No platform dependencies were installed or upgraded in
the user's deployment environment. The final results are recorded in the delivery summary.

## Native Teak URL smoke checks

The existing `openedx-dev:20.0.5` image provides the runtime; the inspected `release/teak.3` source
is mounted read-only. The checks load the actual app registry and resolve native routes, including
copying the real DRF callbacks through the adapter. Discussion routes are enabled in temporary
test settings. This is **not** a substitute for data-backed learner-flow tests.

The exact LMS invocation used the staging source workspace:

```bash
docker run --rm --network none --workdir /tmp \
  --mount type=bind,source=/Users/rldavid/Documents/ChatGPT/openedx_account_lock_ext,target=/plugin,readonly \
  --mount type=bind,source=/Users/rldavid/Dev/skilredi/Openedx/teak/edx-platform,target=/openedx/edx-platform,readonly \
  -e PYTHONPATH=/plugin:/openedx/edx-platform -e DJANGO_SETTINGS_MODULE=lms.envs.test \
  --entrypoint /openedx/venv/bin/python openedx-dev:20.0.5 \
  -c 'import os, runpy; os.makedirs("test_root", exist_ok=True); runpy.run_path("/plugin/tests/teak_runtime_check.py", run_name="__main__")'
```

Use `DJANGO_SETTINGS_MODULE=cms.envs.test` for the CMS variant. For future runs, replace the plugin
mount source with `/Users/rldavid/Dev/skilredi/Openedx/teak/src/openedx-account-lock-ext` and install
the package/ensure its distribution metadata is available so native plugin discovery runs.
The initial image default (`lms.envs.tutor.development`) required absent deployment settings; the
test-settings retry required an isolated `test_root`. Both were addressed without modifying core.

## Tutor and Caddy validation

Tutor configuration was rendered in `/private/tmp/account-lock-tutor`, not the user's Tutor root:

```bash
TUTOR_ROOT=/private/tmp/account-lock-tutor TUTOR_PLUGINS_ROOT=/private/tmp/account-lock-tutor-plugins \
  /private/tmp/account-lock-venv/bin/tutor plugins enable mfe account-lock
TUTOR_ROOT=/private/tmp/account-lock-tutor TUTOR_PLUGINS_ROOT=/private/tmp/account-lock-tutor-plugins \
  /private/tmp/account-lock-venv/bin/tutor config save \
  --set LMS_HOST=learn.example.org --set CMS_HOST=studio.learn.example.org \
  --set MFE_HOST=apps.learn.example.org --set ENABLE_HTTPS=true

docker run --rm --network none \
  --mount type=bind,source=/private/tmp/account-lock-tutor/env/plugins/mfe/apps/mfe/Caddyfile,target=/tmp/AccountLock.Caddyfile,readonly \
  --entrypoint caddy overhangio/openedx-mfe:20.1.0 \
  validate --config /tmp/AccountLock.Caddyfile --adapter caddyfile
```

Caddy reports a valid configuration. Tutor's generated whitespace produces a harmless Caddy
formatting warning. Gateway response/authentication behavior is also exercised by Django tests.

## Still required before deployment acceptance

The data-backed suite is provided in `tests/teak_integration.py` (deliberately not part of standalone
test collection). In an edx-platform test checkout with this package installed and test services
available, run:

```bash
# Run from the edx-platform checkout, preserving its configuration and root fixtures:
DJANGO_SETTINGS_MODULE=lms.envs.test python -m pytest -c setup.cfg -p conftest \
  /path/to/openedx-account-lock-ext/tests/teak_integration.py
```

It exercises real course creation/enrollment and Learning MFE outline views, old reset-token
rejection, and Open edX profile provisioning. Set the normal test MongoDB/MySQL configuration for
your platform test environment, and retain the existing pytest configuration/plugins.

No LMS/CMS, MySQL, MongoDB, Redis, or forum services were running. The full edx-platform suite,
database-backed courseware/assessment/forum integration tests, and a browser-to-gateway-to-LMS
smoke test against the actual deployment were not run. Isolated test containers were automatically
removed; production services were not started, stopped, migrated, or reconfigured.

In staging, enroll a managed user in an allowed course and provision a second disallowed course.
Verify course navigation, content, problem submission, progress, bookmarks, course goals, and
discussion posting. Repeat direct API requests using session, JWT-header, and split-cookie auth.
Verify direct disallowed XBlock handlers and foreign forum IDs fail. Test account/profile entry
URLs on every public MFE origin, including development ports if exposed. Confirm allowed-course
images load, native staff behavior remains unchanged, and old password/email tokens cannot mutate
a newly locked account. Run the same recovery checks through CMS.

Inventory each deployment-specific API and external tool. Protected resource endpoints without
a verified ownership adapter deliberately return denial; add adapters and integration tests for
any such feature the demo requires. Do not declare the deployment fully accepted based solely on
unit tests and URL/configuration smoke checks.
