# Open edX managed demo accounts

`openedx_account_lock_ext` adds managed accounts to Open edX Teak without editing core source.
See [deployment and configuration](docs/deployment.md), [security and route coverage](docs/security.md),
and [validation](docs/validation.md).

This repository contains the Django plugin for LMS and CMS. Tutor gateway integration is maintained
separately in the [Tutor account-lock plugin repository](https://github.com/skilredi/tutor-skilredi-account-lock);
it is not packaged here.

An authenticated member of `locked_account` is restricted unless they are staff or a superuser.
The default course allowlist is empty. Catalog browsing remains available; allowlisting a course
does not enroll a user or bypass normal Open edX course permissions.

Install this package in both LMS and CMS from your package index or from a wheel built from this
source tree. No public PyPI release is assumed.

Create an already activated account inside the LMS:

```bash
./manage.py lms create_locked_user --username demo --email demo@example.org
```

The command prompts for a password twice. For deployment, pipe a secret-manager value to
`--no-input --password-stdin`. There is no plaintext `--password` argument. Password and email
changes for managed accounts are restricted to Django admin and management commands, including
when the learner logs out or has an old recovery token.

## Ulmo runtime dependencies

Provision LMS and CMS with Ulmo's `openedx-platform/requirements` before
installing this plugin. `requirements/base.in` declares its direct runtime
dependencies without version bounds; `pyproject.toml` reads that file for package
metadata. `requirements/base.txt` references those same declarations.

To install from this checkout without changing the platform's shared packages:

```bash
python -m pip install --no-deps .
python -m pip check
```

Exact versions, including Django 5.2.11, DRF 3.16.1, edx-django-utils 8.0.1,
edx-opaque-keys 3.0.0, openedx-filters 2.1.0, and the test-only
edx-drf-extensions 10.6.0, are selected by the Ulmo constraints and compiled
test/quality locks. Install CI tooling in an isolated environment.

## Standalone Ulmo checks and GitHub Actions

The tox and GitHub configuration follows `openedx-lti-provider-ext`, using this
plugin's settings and tests. CI runs `django52`, `custom-user`, `quality`, and
`docs` on Python 3.11 and 3.12 with `ubuntu-latest`.

```bash
python -m pip install -r requirements/pip.txt -r requirements/ci.txt
tox
```

Django is pinned to Ulmo's 5.2.11 in every runtime check. The CI matrix targets
Ulmo; removing package version bounds does not establish support for older releases.
The custom-user tests run
in a separate environment with `tests.custom_settings`. The quality job retains
pylint, pycodestyle, pydocstyle, isort, and mypy. The docs job builds source and
wheel distributions and strictly validates the packaged README with Twine;
this repository has Markdown documentation rather than a Sphinx project.
There are no plugin-owned Django models requiring the LTI PII scanning job,
and the standalone suite needs no platform source checkout.

Shared dependencies are constrained to the local Ulmo platform snapshot in
`requirements/ulmo-constraints.txt`, separately from package metadata. Run
`make upgrade` to regenerate the CI, test, quality, and build locks without
changing that snapshot. All tooling inputs include `constraints.txt`, a small
wrapper containing `-c ulmo-constraints.txt`. The latter consolidates Ulmo's
platform constraints, common constraints, and resolved pins at the recorded
platform commit; no separate common-constraints file is needed. Refresh the
consolidated snapshot when upgrading Ulmo. This applies the platform's bounds
(such as Django <6, pip <25.3, and cryptography <46) during lock generation,
including to packages added later. The quality environment uses Ulmo's
pycodestyle 2.8.0, satisfying the platform's `<2.9` constraint.

GitHub Actions includes commit lint, weekly action updates, requirements update
PRs targeting `develop/ulmo.master`, and release-triggered PyPI publishing.
Coverage uploads use `CODECOV_TOKEN`; publishing requires `PYPI_UPLOAD_TOKEN`.
Requirements bot credentials are optional for the shared upgrade workflow.
No package is published by running tox locally. Standalone checks do not replace
the platform integration and deployment acceptance checks in `docs/validation.md`.
