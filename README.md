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
