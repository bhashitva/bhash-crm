#!/bin/sh
set -eu
name=crm-container-smoke
volume=crm-container-smoke-data
cleanup() {
    docker logs "$name" 2>/dev/null || true
    docker rm -f "$name" >/dev/null 2>&1 || true
    docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker build -t bhash-crm:smoke .
docker run -d --name "$name" --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,exec,size=64m \
    --mount "type=volume,source=$volume,target=/data" \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -p 127.0.0.1:18080:8080 bhash-crm:smoke
attempt=0
until curl -fsS -H 'Host: bhashcrm.bhashitva.org' http://127.0.0.1:18080/healthz; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 30 ] || exit 1
    sleep 1
done
curl -fsS -D /tmp/crm-smoke-headers -o /tmp/crm-smoke-page \
    -H 'Host: bhashcrm.bhashitva.org' http://127.0.0.1:18080/
grep -qi '^Content-Language: hi' /tmp/crm-smoke-headers
grep -q 'lang="hi"' /tmp/crm-smoke-page
grep -q 'id="bhash-source"' /tmp/crm-smoke-page
curl -fsS -H 'Host: bhashcrm.bhashitva.org' \
    http://127.0.0.1:18080/source/signin?language=hi -o /tmp/crm-smoke-source
grep -q 'src/web.bhash' /tmp/crm-smoke-source
grep -q 'src/storage.bhash' /tmp/crm-smoke-source
grep -q 'data-line="1"' /tmp/crm-smoke-source
grep -q 'tok-keyword' /tmp/crm-smoke-source
grep -q 'data-copy-code="true"' /tmp/crm-smoke-source
curl -fsS -H 'Host: bhashcrm.bhashitva.org' \
    http://127.0.0.1:18080/assets/source-copy.js -o /tmp/crm-smoke-copy.js
grep -q 'navigator.clipboard.writeText(code.textContent)' /tmp/crm-smoke-copy.js
docker exec "$name" java -Djdk.httpclient.allowRestrictedHeaders=host \
    -cp /app/healthcheck Healthcheck
echo 'Nonroot container startup, SQLite, Hindi page, and healthcheck passed.'
