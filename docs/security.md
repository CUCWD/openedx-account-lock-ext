# Enforcement and Teak compatibility

## Authorization model

The plugin adds denials; it never grants enrollment, course roles, early access, or visibility.
The group's fixed name is `locked_account`. Only authenticated, nonstaff, nonsuperuser members
are classified as locked. Group queries are request-local and never stored on the platform's
cross-request cached User instance.

Teak's `has_access()` has no general plugin denial filter. The implementation therefore combines
its existing `CourseEnrollmentStarted` filter with request enforcement and ownership adapters.
It does not monkeypatch `has_access`, replace an authentication backend, or change core files.
Native view permissions, object permissions, authentication, CSRF, and throttling remain in force.

DRF authentication runs within the view, so checking Django's initial `request.user` alone is
insufficient. The adapter creates a local subclass that checks policy after the original
`initial()` method, and redacts permitted bootstrap responses before rendering. It copies the
callback closure chain to substitute that subclass while retaining outer decorators and attributes.
It does not mutate shared view classes. This adapter is version-sensitive and tested against DRF
3.15.2; retest it on a release upgrade. Unsupported callback layouts fail rather than silently skip
the guard. System checks require the guard to follow every native view middleware.

## Route inventory

| Surface | Ownership/enforcement |
| --- | --- |
| `/courses/{course_id}/...` including courseware, progress, grades, tabs and legacy discussions | Resolved course kwargs; inconsistent usage keys or other supplied IDs are denied |
| Course-home, learning-sequence and other APIs with `course_key_string`/`course_id` kwargs | Canonical resolved course key; normal view authorization still applies |
| `/api/courses/v1/blocks/`, v2, and block metadata/tree routes | Registered query `course_id` or resolved usage key |
| `/xblock`, `/xblocks`, `/api/xblock`, course XBlock handler and public-video routes | Course owned by the resolved usage key |
| `/api/enrollment/v1/enrollment`, `/change_enrollment`, unenroll | Registered form/JSON identifiers; enrollment creation also checked by the platform filter |
| `/api/bookmarks/v1/bookmarks/` | Query course key or submitted/resolved usage key; unscoped lists denied |
| Course goal save/dismiss operations | Registered JSON `course_id` |
| `/api/discussion/...` thread/comment resources | Server-side forum lookup of the resource's course; supplied course IDs must agree |
| Mobile course routes with resolved course kwargs | Same course policy; unscoped protected mobile resources denied |
| `asset-v1:` and versioned asset URLs | Embedded asset course key, including Teak's `/assets/courseware/[vN/]digest` prefix |
| Legacy `c4x` asset URLs lacking a run | Denied; migrate to course-run-specific asset URLs |
| Catalog list/course-ID endpoints, learner-home initialization and enrollment listing | Browsing permitted; opening disallowed content remains blocked |
| Account APIs and deprecated profile-image upload/remove APIs | Writes denied; reads denied except the documented bootstrap/localization exceptions |
| Password reset initiation, old/new token routes, primary/secondary email confirmation | Target-account lookup works even without a logged-in session |
| Account/profile and learning MFE entry paths | Caddy forwards authorization before serving the MFE |

The initial deployment also contains `skilredi-keyterms-app`. Its course endpoints select data
by course number rather than a course-run key, and its glossary returns every course's terms.
`/api/keyterms` is protected. To permit its course-term listing, configure an explicit mapping:

```python
OPENEDX_ACCOUNT_LOCK_COURSE_NUMBER_MAP = {
    "YOUR_COURSE_NUMBER": "course-v1:YourOrg+Demo101+2026",
}
```

The global glossary and unscoped term writes remain denied for managed accounts. A course number
must map to the actual owning run; do not infer ownership from a display label.

Unknown resource-based routes under protected prefixes fail closed. In particular, adding
`?course_id=allowed` to an exam/attempt/other object endpoint does not authorize that object.
Only explicitly inventoried list/create endpoints accept a client-supplied course selector.
Additional resource adapters are needed for independently configured proctoring, external
discussion providers, or custom APIs that expose identifiers without course ownership. XBlock
handlers with course/usage keys continue to support normal in-course assessments.

## Extending ownership coverage

Add a new namespace to `OPENEDX_ACCOUNT_LOCK_COURSE_API_PREFIXES`, preserving the defaults.
Configure `OPENEDX_ACCOUNT_LOCK_COURSE_RESOLVERS` with dotted callables accepting `(request, kwargs)`.
Each returns a course key after a server-side lookup, returns `None` when not applicable, or raises
`UnresolvedCourse` when ownership cannot be established. Every resolved/supplied key must agree.
These functions are trusted application code; never just echo arbitrary query parameters for
object endpoints. Add integration tests for both allowed and disallowed ownership before enabling.

## Credentials and recovery

Known reset-initiation routes return Teak's generic completion response without sending managed
account reset mail. Reset tokens and pending primary/secondary email-change records are checked
against their target user; old tokens do not bypass a newly added group membership.

A request-scoped user `pre_save` safeguard additionally rejects primary email/password changes
on existing managed users outside authenticated staff Django-admin requests. It covers ordinary
model saves by routes not explicitly inventoried. Offline management commands are permitted.
It does not turn a staff user's public API call into an administrator exception. Native admin
permissions still determine which staff users may edit which records.

This is not a database trigger. Arbitrary application code using `QuerySet.update()`, raw SQL,
external identity-provider writes, or asynchronous jobs must honor this policy separately.
Do not use public password-reset flows to administer these accounts. Primary account/email
registration and external SSO linking should be restricted operationally to your chosen demo
identities; this plugin is not an identity-provider policy engine.

## Deployment boundaries

- Check both LMS and CMS and inspect the **effective** settings, not just common.py.
- Serve account/profile and learning MFEs only through the configured gateway; direct webpack
  ports or alternate static origins bypass the entry-page gate. APIs remain protected.
- Already downloaded/browser-cached frontend shells cannot be revoked by Django or Caddy.
  Group changes take effect on subsequent backend requests and fresh gateway navigation.
- Public CDN/static assets, public videos accessed anonymously, external LTI tools, and content
  copied before locking are not made confidential by this plugin. The objective is authenticated
  demo-account restrictions, not DRM or a site-wide anonymous-access policy.
- Course allowlisting does not grant enrollment or disable existing Open edX permissions.
- Use isolated demo courses/accounts for assessment previews; allowed course interactions retain
  their ordinary persistence and side effects.
- Retest route inventory, callback adaptation, JWT behavior, and gateway routing for every
  platform or custom-plugin upgrade. Do not treat standalone tests as full deployment acceptance.
