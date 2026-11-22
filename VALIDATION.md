# Verification record — November 21, 2026

The standalone repository builds using the official Bhash 0.28.0 compiler JAR,
verified against compiler.lock.json. No compiler source checkout is required.

| Check | Result |
| --- | --- |
| JVM + SQLite HTTP integration suite | Passed, 20 scenario groups including source highlighting and copy controls |
| .NET CLR + SQLite HTTP integration suite | Passed, 20 scenario groups including source highlighting and copy controls |
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

All four jobs also pass for highlighting/copy commit `4786c7d`:
https://github.com/bhashitva/bhash-crm/actions/runs/44967799934
The renderer tests cover keywords, types, literals, function names, Devanagari
numbers, escaped strings, multiline comments, line numbering, and inert HTML.
HTTP tests reconstruct highlighted files exactly, including indentation and
trailing newlines. The generated clipboard bridge is tested with the exact
Unicode payload, success/reset behavior, denied access and manual selection.
Browser checks confirm colors, gutters, nested-file controls and localized copy
feedback. Clipboard writes are user-initiated; the bridge never reads it.

Runtime `4786c7d` is live. HTTPS checks pass for every source mapping in Hindi
and English, numbered/highlighted shared files, exact reconstructed source text,
localized copy controls and the generated bridge's regression scenarios. The
container is healthy; its original data volume, SQLite integrity and foreign
keys are verified. Existing playground and Kanboard sites return HTTP 200.

Public signup runtime `42a5c62` is live. All four CI jobs pass, including
Windows/Linux JVM, Linux CLR and the production container:
https://github.com/bhashitva/bhash-crm/actions/runs/44972412115

The additional signup suite uses explicit local provider doubles, never real
emails or a production CAPTCHA bypass. It verifies missing/incorrect checks,
hostname/action/session binding, replay rejection, delivery failure, normalized
unique emails, hashed expiring links, harmless scanner GETs, cross-browser
completion, password validation, CSRF/session rotation, rejected extra fields,
isolated owner tenants, concurrent single-use completion, preserved legacy
credentials, durable per-email/global limits across restart, new source mappings,
and rejection of local test transport in production mode. Local sandbox network
timeouts were resolved by running the final HTTP suite with unrestricted loopback
networking; the unchanged suite passes on both CI operating systems.

Before rollout, a verified online backup was migrated in an isolated container
using a private copy of the actual live database. Existing user identifiers,
password hashes, active flags, language preferences, memberships, tenant and
CRM record counts were preserved. After activation, original credentials,
SQLite integrity, foreign keys, HTTPS Hindi signup, headers, playground and
Kanboard were checked again.

Cloudflare's hostname-restricted Managed widget and a sending-only Resend key
restricted to `bhashitva.org` are configured privately on the VPS. Resend reports
the domain verified; the three additive DNS records preserve every original
record, including Titan MX/SPF/DKIM and the Microsoft verification record.
The conflicting legacy proxy Referrer-Policy was removed for the CRM alone,
after backup and Caddy validation; the app now supplies `strict-origin`, which
protects link tokens while retaining browser form Origin checks.

A real browser passed the live Managed check and submitted the approved single
test to `info@bhashitva.org`. The CRM displayed its Hindi check-email page;
Resend confirmed Delivered with the Hindi verification subject. The source
drawer opened highlighted signup code and closed without navigation. No real
account was created during this check: the recipient can complete the emailed
link and choose credentials privately. Account creation and link consumption
are covered by the disposable-database integration tests.

Hindi-name runtime `e080b2e` is live. All four checks pass:
https://github.com/bhashitva/bhash-crm/actions/runs/44973922315
Signup and sign-in now accept Hindi full names with spaces, Devanagari digits,
vowel marks and conjuncts. Tests register a Hindi username exceeding 64 UTF-8
bytes, preserve its Hindi organization, sign in using canonical nukta and
conjunct-shaping variants, accept a 64-character Hindi username, and reject
65-character names, leading marks, stray invisible characters and markup.
Legacy Latin accounts still authenticate. Windows launcher checks cover the
same names with both UTF-8 and Windows-1252 Java source encodings.

The candidate passed a private live-database copy check, preserving existing
accounts, password hashes, email verification state, organizations, memberships,
CRM records and pending email links without a schema change. A verified online
backup precedes deployment. Post-rollout HTTPS checks confirm the new validator
and registration guidance in the running source snapshot, original credentials,
database integrity, and the unaffected playground and Kanboard services.
