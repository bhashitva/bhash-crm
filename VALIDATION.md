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
| Docker image build/runtime | Not yet run locally; Docker engine unavailable |
| Live VPS/DNS/HTTPS deployment | Must be recorded after actual deployment |
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

All verification uses disposable databases. No personal CRM database, production
password, Hostinger credential, SSH key or GitHub token is part of the source.
