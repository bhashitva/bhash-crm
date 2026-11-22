# Verification record — November 21, 2026

The standalone repository builds using the official Bhash 0.28.0 compiler JAR,
verified against compiler.lock.json. No compiler source checkout is required.

| Check | Result |
| --- | --- |
| JVM + SQLite HTTP integration suite | Passed, 19 scenario groups including source viewer |
| .NET CLR + SQLite HTTP integration suite | Passed, 19 scenario groups including source viewer |
| Bhash UI/form/local-origin policy tests | Passed |
| Schema-v2 to schema-v3 account/data migration | Passed |
| Java launcher/password boundary checks | Passed |
| Hindi stdout/stderr encoding regression | Passed |
| Interrupted bootstrap/retry preservation | Passed |
| Source dependency lockfiles | Verified |
| Source panel and shared code documents | Passed on all CRM page mappings, Hindi/English, and error pages |
| Browser interaction | Verified open/close, nested source loading, keyboard close, and retained unsaved input |
| Highlighting and copy enhancement | Bhash lexer/escaping checks and exact highlighted-source round trips pass; generated clipboard bridge payload/success/failure checks pass |
| CI workflow actionlint validation | Passed |
| Docker image build/runtime | Passed on VPS and Ubuntu CI, nonroot/read-only with SQLite |
| Live VPS/DNS/HTTPS deployment | Passed at https://bhashcrm.bhashitva.org on November 21, 2026 |
| Production load/failover test | Not performed |

The source viewer uses native disclosures and lazy same-origin frames. Browser
checks confirm frontend/backend and shared source display, keyboard close,
mobile drawer sizing, unchanged record URL, and preservation of unsaved notes.
HTTP checks cover every rendered CRM page, localized controls, source selection,
escaped code, unknown source rejection, error pages, and absence of customer
records and credentials from the source documents. The generated catalog is
checked against the source files before CI builds.

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

The source-viewer update is deployed from runtime commit `54e9ba6`. Public HTTPS
checks cover each source-page mapping in both languages, shared code documents,
the login-page control, invalid source rejection, and 404/405 controls. The
existing database volume and integrity checks pass; the old sites return 200.
A verified online backup precedes the update. The application serves fixed
build-time Bhash source; it reads no runtime files through the source routes.

All four updated CI jobs pass for commit `6717676` (Ubuntu JVM, Windows JVM,
Ubuntu CLR, and the production container):
https://github.com/bhashitva/bhash-crm/actions/runs/44954809698
