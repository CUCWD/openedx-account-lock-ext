# Open edX managed demo accounts

`openedx_account_lock_ext` adds managed accounts to Open edX Teak without editing core source.
See [deployment and configuration](docs/deployment.md), [security and route coverage](docs/security.md),
and [validation](docs/validation.md).

An authenticated member of `locked_account` is restricted unless they are staff or a superuser.
The default course allowlist is empty. Catalog browsing remains available; allowlisting a course
does not enroll a user or bypass normal Open edX course permissions.

The package includes an Open edX Django plugin and an optional Tutor 20 plugin named `account-lock`.
Install the Django package in both LMS and CMS; install the Tutor extra in the Tutor host environment.
Enable the Tutor integration to protect independently served account/profile and learning MFE routes.

```bash
pip install 'openedx-account-lock-ext[tutor]'
tutor plugins enable account-lock
```

The package must first be built/distributed or installed from this source directory; the example above
assumes your package index contains your published build. It does not claim a public PyPI release exists.

Create an already activated account inside the LMS:

```bash
./manage.py lms create_locked_user --username demo --email demo@example.org
```

The command prompts for a password twice. For deployment, pipe a secret-manager value to
`--no-input --password-stdin`. There is no plaintext `--password` argument. Password and email
changes for managed accounts are restricted to Django admin and management commands, including
when the learner logs out or has an old recovery token.
