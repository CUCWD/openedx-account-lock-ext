Change Log
##########

0.1.0 (unreleased)
******************

Added
=====

* Provide managed-account restrictions, course allowlisting, credential-change
  protection, MFE gateway authorization, and account provisioning commands.
* Add standalone tests, custom-user-model checks, and Python quality checks.
* Add GitHub Actions for Python 3.11/3.12 with Ulmo's Django 5.2.11, package
  validation, release publishing, commit checks, and dependency maintenance.
* Include this changelog in source and wheel distributions.

Fixed
=====

* Route dashboard fixtures through the learner-course view and authenticate
  managed-user gateway requests in standalone tests.
* Test missing and unsupported Accept headers separately, preserving native DRF
  content-negotiation denials.
* Use the configured default learner dashboard when an operator's fallback
  URL is unsafe, retaining destination checks to prevent redirect loops.
* Align redirect expectations with the trailing slash in the default URL.
* Remove a redundant configuration-check local variable to satisfy Pylint.

Changed
========

* Define the package version in ``openedx_account_lock_ext/__init__.py`` and
  read it from ``pyproject.toml`` when building distributions.
* Read unpinned runtime dependencies from ``requirements/base.in`` so the host
  edx-platform environment controls their versions.
* Consolidate Ulmo's platform constraints, common constraints, and resolved pins
  in ``requirements/ulmo-constraints.txt``, referenced by ``constraints.txt``.
* Generate isolated test and tooling locks under the Ulmo constraints.
* Use equivalent URL formatting compatible with Ulmo's pycodestyle checker on
  Python 3.12.
