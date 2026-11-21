# Bhash web application platform

A versioned source library for Bhash-authored multi-tenant web applications.
Application screens, forms, routing, authorization and storage are Bhash source.
The renderer produces HTML and a framework stylesheet. JavaScript is unnecessary;
the example works when scripts are disabled by Content Security Policy.

## Consume the package

```properties
name=my-app
sources=src
dependency.platform.path=../../packages/web-platform
dependency.platform.version=0.1.0
```

Run `deps lock <app> --offline` and commit the resulting lockfile. No compiler
changes, runtime downloads, or framework code generation are required. See the
[complete CRM](../../README.md) and
[architecture and remaining work](../../deploy/README.md).

## Public surface

| Type | Purpose |
| --- | --- |
| `दृश्य` | Escaped HTML trees, labels, inputs, selects, links, forms, pages and redirects |
| `फॉर्म` | Bounded UTF-8 URL-encoded form decoding; duplicate fields rejected |
| `फॉर्मसुरक्षा` | Form-token adapter over the existing Host/Origin/Fetch Metadata/CSRF policy |
| `डेटास्रोत` | SQLite or PostgreSQL connections with explicit resource ownership |
| `स्थायीसत्र` | Database-backed `सत्रप्रबंधक` implementation with shared revocation and expiry |
| `मंच` | Platform migration prefix and database-backed login attempt limits |
| `संगठनसंदर्भ` | Tenant, authenticated actor and current membership role |
| `संगठननीति` | Live membership/session checks, tenant write locks and transactional audit entries |

```text
आयात अनुप्रयोग.दृश्य;

स्थिर फ: दृश्य = दृश्य.फॉर्म("/contacts/save", सत्रमान.सीएसआरएफ())
    .जोड़ो(दृश्य.क्षेत्र("name", "Contact name", "text", ""))
    .जोड़ो(दृश्य.भेजो("Save contact"));
स्थिर उत्तर: वेबउत्तर = दृश्य.पृष्ठ("New contact", फ);
```

HTML nodes and attributes use allowlists. Text and attribute values are escaped.
There is no raw HTML entry point, executable event attribute or external-link
escape hatch. Same-origin links and form actions must start with a single `/`.
Application code owns its SQL; request values always use bound parameters.

## Persistence contract

Append application migrations to `मंच.माइग्रेशनलो()` and apply the complete
immutable plan at startup. The prefix owns `platform_*` tables. Do not apply a
shorter prefix after application migrations have been installed.

`स्थायीसत्र` uses the same database as tenants, accounts and memberships. Only
SHA-256 digests of 256-bit random bearer tokens are stored. CSRF secrets are
independent random values. Login rotates both values and revokes the previous
session; logout deletes the row. Sessions remain valid after process shutdown.
Expiry is 30 minutes idle / eight hours absolute. Capacity is 10,000 live sessions
across workers. Roles are read from current membership, never cached in sessions.
Session APIs deliberately reject nonempty role lists: use `संगठननीति` for roles.

In explicit local-development mode only, the manager accepts `localhost` and
`127.0.0.1` on the configured port. It selects the origin policy by the exact
Host header, then requires any Origin to match that host. Cross-alias submissions,
other ports, suffix lookalikes and arbitrary hosts are rejected. Production
retains the single configured HTTPS origin; development aliases are not enabled.

Persistent expiry uses Unix epoch milliseconds. Workers require synchronized
clocks. Concurrent touches preserve the greatest timestamp already stored.
A request before its session's creation timestamp fails closed. Later backwards
clock jumps can extend idle validity up to the absolute lifetime; forward jumps
can expire sessions. This is not a monotonic distributed-clock protocol.

Use `संगठननीति.तालालो` and then `जाँचो` inside the same transaction as a mutation.
Membership changes must use the same tenant lock. Every tenant-owned read and
write must bind the tenant ID obtained from this authorization step. The library
cannot enforce tenant scoping on arbitrary application SQL.

## Verify

```sh
java -jar target/bhash-compiler-0.1.0-SNAPSHOT.jar deps verify packages/web-platform/tests
java -jar target/bhash-compiler-0.1.0-SNAPSHOT.jar compile packages/web-platform/tests -o target/platform-tests.jar
java -jar target/platform-tests.jar
```

The CRM's HTTP suite checks the database-backed components with real compiled
servers, including multiple processes. It uses disposable data only.
