# VPS deployment: bhashcrm.bhashitva.org

This app is a JVM service. It can run next to existing VPS sites. The templates
use backend port **8092**, loopback-only on the host, with a TLS reverse proxy.
Do not replace another site's proxy configuration or publish the backend port.

## Docker Compose

On the VPS, with Docker/Compose already installed:

```sh
git clone https://github.com/bhashitva/bhash-crm.git
cd bhash-crm
cp .env.example .env
docker compose --env-file .env -f deploy/compose.yaml up -d --build
docker compose --env-file .env -f deploy/compose.yaml ps
```

The image builds Bhash source with the checksum-pinned compiler. The runtime is
Java 17, running as UID/GID 10001 with a read-only root filesystem. A named volume
holds `/data/crm.db`. `/tmp` is bounded and executable because SQLite's JDBC
driver extracts and loads its bundled native library there. No Docker socket is
mounted. The application listens on the container interface only in explicit
production mode; the published host port remains bound to 127.0.0.1.

The production origin is `https://bhashcrm.bhashitva.org`. TLS verification and
CSRF/Host/Origin checks stay enabled. Set `.env` values before changing that
hostname; `CRM_PUBLIC_HOST` must match the public Host header, including a
nondefault port if one is used.

## Initial owner

Provision over an SSH terminal; passwords are read without echo and passed to
the short-lived provisioning process through its environment, not command-line
arguments or a committed file:

```sh
read -r -p 'Owner username: ' BHASH_CRM_USER
read -r -p 'Organization name: ' BHASH_CRM_TENANT
read -r -s -p 'Password (12+ characters): ' BHASH_CRM_PASSWORD
printf '\n'
export BHASH_CRM_USER BHASH_CRM_TENANT BHASH_CRM_PASSWORD
docker compose --env-file .env -f deploy/compose.yaml exec \
  -e BHASH_CRM_USER -e BHASH_CRM_TENANT -e BHASH_CRM_PASSWORD crm \
  java -Dfile.encoding=UTF-8 -jar /app/crm.jar --db=/data/crm.db --bootstrap=true
unset BHASH_CRM_USER BHASH_CRM_TENANT BHASH_CRM_PASSWORD
```

Existing accounts are not reset. A failed setup can be retried with a valid
password. If migrating an existing database, back it up and stop its writer
before transferring it; retain its password hashes and file permissions. The
source repository intentionally contains no personal database or initial login.

## DNS and HTTPS

1. Read the existing DNS zone and identify the VPS's actual address.
2. Add an A record for `bhashcrm.bhashitva.org` pointing at that IPv4 address.
   Add AAAA only if the VPS and proxy serve that IPv6 address. Preserve MX,
   verification and all other existing records.
3. Add the block in [Caddyfile](Caddyfile) to the existing proxy configuration.
   Validate the full Caddy configuration before reloading it. Keep other sites.
4. Caddy obtains/renews the certificate and forwards the original Host and Origin.
5. Verify the public certificate, Hindi login page, authenticated actions and
   profile preferences at `https://bhashcrm.bhashitva.org`.

If the existing proxy is Nginx, adapt [nginx.conf](nginx.conf) instead. Do not run
a second proxy on occupied ports 80/443. The included Caddy block assumes Caddy
runs on the host; a containerized proxy needs a shared network or another
explicitly configured reachable upstream.

For the existing Docker Caddy gateway on this VPS, start the CRM with both files:

```sh
docker compose -f deploy/compose.yaml -f deploy/compose.gateway.yaml up -d --build
```

The override joins the external `bhash-playground_public` network with the unique
alias `bhash-crm`. Set `CRM_GATEWAY_NETWORK` if that network has a different name.
Append a new `bhashcrm.bhashitva.org` site to the existing gateway's Caddyfile with
`reverse_proxy bhash-crm:8080`, validate it, and reload Caddy. Keep the existing
site blocks, volumes, and gateway container. The CRM database volume is separate.

## Without Docker

Use `sh build.sh`, a dedicated `bhash-crm` Unix account, `/opt/bhash-crm` for the
checkout and `/var/lib/bhash-crm` for its private database. Adapt the included
[systemd service](bhash-crm.service). Install the service, reload systemd and
enable/start it only after account provisioning and proxy configuration have
been reviewed on the target host.

## Backups and upgrades

Take a consistent backup before each upgrade. One simple option is to stop this
app alone, copy **all** of `/data` (including any SQLite journals), then start it:

```sh
mkdir -p backups
docker compose --env-file .env -f deploy/compose.yaml stop crm
docker compose --env-file .env -f deploy/compose.yaml cp crm:/data/. backups/
docker compose --env-file .env -f deploy/compose.yaml start crm
```

Keep backups encrypted and access restricted, and test restoration. Backups are
ignored by Git. Preserve the named volume on redeployment; never use
`docker compose down --volumes` for an upgrade. Pull a reviewed commit and rebuild
the app image. Schema migrations are explicit, checksum-validated and forward-only.
Returning to an older schema version requires restoring its compatible backup.

## Scope and verification

The Compose/Caddy/systemd files are deployment templates. Their presence does
not prove a live deployment has completed. Record the actual VPS, deployed commit,
DNS/certificate result and authenticated smoke-test outcome after deployment.
No user-count or high-availability claim is implied by shared session storage.
