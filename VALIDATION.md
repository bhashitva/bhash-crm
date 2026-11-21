# Verification record — November 21, 2026

The standalone repository builds using the official Bhash 0.28.0 compiler JAR,
verified against compiler.lock.json. No compiler source checkout is required.

| Check | Result |
| --- | --- |
| JVM + SQLite HTTP integration suite | Passed, 18 scenario groups |
| .NET CLR + SQLite HTTP integration suite | Passed, 18 scenario groups |
| Bhash UI/form/local-origin policy tests | Passed |
| Schema-v2 to schema-v3 account/data migration | Passed |
| Java launcher/password boundary checks | Passed |
| Hindi stdout/stderr encoding regression | Passed |
| Interrupted bootstrap/retry preservation | Passed |
| Source dependency lockfiles | Verified |
| CI workflow actionlint validation | Passed |
| Docker image build/runtime | Passed on VPS and Ubuntu CI, nonroot/read-only with SQLite |
| Live VPS/DNS/HTTPS deployment | Passed at https://bhashcrm.bhashitva.org on November 21, 2026 |
| Production load/failover test | Not performed |

The HTTP suite covers Hindi defaults, temporary session-language switches,
persisted per-user default language, preference isolation across users and workers,
re-login, unsupported locale rejection, preference overposting/CSRF rejection,
unchanged customer text, both localhost aliases, tenant isolation, role revocation,
concurrent edits, archive/restore relationships, pagination, persistent sessions,
restart, shared login limits, password changes and secure production cookies.

The migration fixture creates an actual version-2 database before the new app
runs its migrations. Existing password hashes, organizations, memberships and a
Hindi customer record remain intact, and the existing account can sign in with
Hindi as its new default language.

The automated suites use disposable databases. Live deployment checks also
verify the approved database transfer: account identifiers, password hashes,
active flags and record counts match the pre-migration snapshot; integrity and
foreign-key checks pass; the existing user defaults to Hindi. Local sessions
were excluded, requiring a fresh hosted login. Interactive sign-in using the
owner's password remains for the owner to check.

Live HTTPS checks pass for the Hindi login page, language switching in both
directions, independent sessions, Secure/HttpOnly cookies, and cross-origin POST
rejection. All pre-existing DNS records match the saved zone. The existing
playground and Kanboard sites return HTTP 200.

All four CI jobs pass for runtime commit `8372456`:
https://github.com/bhashitva/bhash-crm/actions/runs/44950942478

No personal database, password, Hostinger credential, SSH key or GitHub token is
part of the source repository.
