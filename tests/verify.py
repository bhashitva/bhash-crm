#!/usr/bin/env python3
"""Exercise the compiled Bhash application over real HTTP; no Python app server.

python examples/multi-tenant-crm/verify.py --jar target/crm.jar
Uses only the Python standard library and a disposable SQLite database.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import html.parser
import http.cookiejar
import json
import os
from pathlib import Path
import queue
import secrets
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Inputs(html.parser.HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.values = {}
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and "name" in attrs:
            self.values.setdefault(attrs["name"], attrs.get("value", ""))
        if tag == "a":
            self.links.append(attrs.get("href", ""))


class Server:
    def __init__(self, command, database, *, provider="sqlite", origin=None, port=0):
        self.events = queue.Queue()
        self.logs = []
        command = [*command, f"--db={database}", f"--port={port}", f"--provider={provider}"]
        command += [f"--origin={origin}"] if origin else ["--local=true"]
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True,
                                        encoding="utf-8", errors="replace")
        for stream in (self.process.stdout, self.process.stderr):
            threading.Thread(target=self.drain, args=(stream,), daemon=True).start()
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                line = self.events.get(timeout=.2)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise AssertionError("Server exited: " + "\n".join(self.logs))
                continue
            if line.startswith("READY "):
                # The listener is bound before READY, and accept starts immediately.
                self.origin = f"http://127.0.0.1:{int(line.split()[1])}"
                return
        self.stop()
        raise AssertionError("Server did not become ready")

    def drain(self, stream):
        for line in stream:
            self.logs.append(line.rstrip())
            self.events.put(line.rstrip())

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


class Client:
    def __init__(self, server, cookies=None, *, origin=None):
        self.origin = origin or server.origin
        self.cookies = cookies if cookies is not None else http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.cookies), NoRedirect())
        self.csrf = ""

    def request(self, path, *, data=None, raw=None, status=200, headers=None):
        hdr = {}
        body = None
        if data is not None or raw is not None:
            body = raw if raw is not None else urllib.parse.urlencode(data).encode()
            hdr = {"Origin": self.origin,
                   "Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            hdr.update(headers)
        req = urllib.request.Request(self.origin + path, data=body, headers=hdr)
        try:
            response = self.opener.open(req, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        text = response.read().decode("utf-8")
        assert response.code == status, (path, response.code, status, text[:500])
        if status == 200 and response.headers.get_content_type() == "text/html":
            assert response.headers["Cache-Control"] == "no-store"
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert "<script" not in text.lower(), "Bhash SSR must work with scripts disabled"
            token = Inputs(text).values.get("_csrf")
            if token:
                self.csrf = token
        return text, response.headers

    def post(self, path, values, status=303, **kw):
        return self.request(path, data={"_csrf": self.csrf, **values}, status=status, **kw)

    def login(self, name, password, language="en"):
        self.request("/")
        old = self.csrf
        self.post("/login", {"username": name, "password": password})
        self.request("/")
        assert self.csrf != old, "CSRF token must rotate on login"
        if language is not None:
            self.post("/language", {"language": language, "_return": "/"})
            self.request("/")

    def create(self, tenant, kind, name, **values):
        text, headers = self.post(f"/t/{tenant}/{kind}/save", {
            "id": "", "version": "0", "name": name, "stage": "open", **values})
        return headers["Location"].rsplit("/", 1)[1]



class PostgresConnection:
    def __init__(self):
        if os.environ.get("BHASH_CRM_TEST_POSTGRES") != "true":
            raise RuntimeError("Set BHASH_CRM_TEST_POSTGRES=true and supply an empty dedicated PostgreSQL test database")
        import psycopg  # Optional PostgreSQL test dependency, never part of the app.
        self.connection = psycopg.connect(
            host=os.environ.get("BHASH_PG_HOST", "localhost"),
            port=os.environ.get("BHASH_PG_PORT", "5432"),
            dbname=os.environ.get("BHASH_PG_DATABASE", "bhash_crm"),
            user=os.environ.get("BHASH_PG_USER", "bhash"),
            password=os.environ.get("BHASH_PG_PASSWORD", ""),
            sslmode=os.environ.get("BHASH_PG_SSLMODE", "verify-full"),
            **({"sslrootcert": os.environ["BHASH_PG_CA"]} if os.environ.get("BHASH_PG_CA") else {}),
            autocommit=True,
        )

    def execute(self, sql, values=()):
        return self.connection.execute(sql.replace("?", "%s"), values)

    def close(self):
        self.connection.close()

    def commit(self):
        self.connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def connect_database(database, provider):
    return sqlite3.connect(database) if provider == "sqlite" else PostgresConnection()


def verify(command, artifact: Path, provider: str, runtime: str, report: Path | None):
    checks = []
    servers = []
    with tempfile.TemporaryDirectory(prefix="bhash-crm-", dir=artifact.parent) as tmp:
        database = Path(tmp) / "crm.db"
        password = "Test-" + secrets.token_hex(12)
        for username, tenant in (("alice", "Alpha"), ("bob", "Beta")):
            env = {**os.environ, "BHASH_CRM_USER": username,
                   "BHASH_CRM_PASSWORD": password, "BHASH_CRM_TENANT": tenant}
            result = subprocess.run([*command, f"--db={database}", f"--provider={provider}", "--bootstrap=true"], env=env,
                                    capture_output=True, text=True, encoding="utf-8", timeout=40)
            assert result.returncode == 0, result.stderr
        connection = connect_database(database, provider)
        tenants = dict(connection.execute("SELECT name,id FROM platform_tenants"))
        alpha, beta = tenants["Alpha"], tenants["Beta"]
        try:
            first = Server(command, database, provider=provider)
            servers.append(first)
            alice, bob = Client(first), Client(first)
            alice.login("alice", password)
            bob.login("bob", password)
            checks.append("bootstrap and authenticated Bhash pages")

            localhost_origin = first.origin.replace("127.0.0.1", "localhost")
            localhost = Client(first, origin=localhost_origin)
            localhost.login("alice", password)
            localhost.request(f"/t/{alpha}/contacts")
            localhost.create(alpha, "tasks", "Created using localhost")
            localhost.post("/tenants", {"name": "rejected alias-origin mismatch"},
                           headers={"Origin": first.origin}, status=403)
            alice.post("/tenants", {"name": "rejected reverse alias-origin mismatch"},
                       headers={"Origin": localhost_origin}, status=403)
            localhost.request("/", headers={"Host": "localhost.evil.example"}, status=403)
            localhost.request("/", headers={"Host": "localhost:1"}, status=403)
            localhost.post("/logout", {})
            text, _ = localhost.request("/")
            assert 'action="/login"' in text
            alice.request(f"/t/{alpha}/contacts")
            checks.append("localhost and 127.0.0.1 login/write/logout with strict matching origins")

            css, headers = alice.request("/assets/platform.css")
            assert headers.get_content_type() == "text/css" and "@media" in css
            for kind in ("companies", "contacts", "deals", "tasks"):
                alice.request(f"/t/{alpha}/{kind}")
                alice.request(f"/t/{alpha}/{kind}/new")
            company = alice.create(alpha, "companies", "Acme हिंदी")
            name = '<script>alert("x")</script> O\'Reilly हिंदी'
            contact = alice.create(alpha, "contacts", name, email="hello@example.org",
                                   phone="+1 555 1234", notes="First line\nदूसरी पंक्ति",
                                   related_id=company)
            deal = alice.create(alpha, "deals", "Renewal", related_id=contact,
                                amount_minor="123456", currency="INR")
            task = alice.create(alpha, "tasks", "Call customer", related_id=contact,
                                due_date="2026-12-01")
            for kind, record in (("companies", company), ("contacts", contact),
                                  ("deals", deal), ("tasks", task)):
                alice.request(f"/t/{alpha}/{kind}/{record}")
            text, _ = alice.request(f"/t/{alpha}/contacts/{contact}")
            assert "&lt;script&gt;" in text and "दूसरी पंक्ति" in text
            text, _ = alice.request(f"/t/{alpha}")
            assert "INR 1234.56" in text
            checks.append("companies, contacts, deals, tasks, exact minor units, Hindi and escaped HTML")

            anonymous = Client(first)
            text, headers = anonymous.request("/")
            assert headers["Content-Language"] == "hi" and '<html lang="hi">' in text
            assert "आपके ग्राहक प्रबंधन का कार्यस्थल" in text and "Sign in to manage" not in text
            anonymous.post("/language", {"language": "en", "_return": "/"})
            text, headers = anonymous.request("/")
            assert headers["Content-Language"] == "en" and "Your customer workspace" in text
            assert dict(connection.execute("SELECT username,ui_language FROM platform_users")) == {"alice": "hi", "bob": "hi"}

            alice.post("/language", {"language": "hi", "_return": "/account"})
            for path in ("/", "/account", f"/t/{alpha}", f"/t/{alpha}/contacts",
                         f"/t/{alpha}/contacts/{contact}", f"/t/{alpha}/members", f"/t/{alpha}/audit"):
                text, headers = alice.request(path)
                assert headers["Content-Language"] == "hi" and '<html lang="hi">' in text
                assert ">Sign out<" not in text and ">Account<" not in text
            untranslated = alice.create(alpha, "contacts", "Contacts")
            text, _ = alice.request(f"/t/{alpha}/contacts/{untranslated}")
            assert 'value="Contacts"' in text, "Customer text must not be translated as a UI label"
            alice.post("/account/preferences", {"language": "en"})
            text, headers = alice.request("/account")
            assert headers["Content-Language"] == "en" and "Language preference" in text
            assert connection.execute("SELECT ui_language FROM platform_users WHERE username='alice'").fetchone()[0] == "en"
            alice.post("/language", {"language": "hi", "_return": "/"})
            assert connection.execute("SELECT ui_language FROM platform_users WHERE username='alice'").fetchone()[0] == "en", "Session switching must not silently change the saved default"
            fresh_alice, fresh_bob = Client(first), Client(first)
            fresh_alice.login("alice", password, language=None)
            fresh_bob.login("bob", password, language=None)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(fresh_alice.request, "/account"), pool.submit(fresh_bob.request, "/account")]
                results = [future.result(timeout=30) for future in futures]
            assert results[0][1]["Content-Language"] == "en" and "Your account" in results[0][0]
            assert results[1][1]["Content-Language"] == "hi" and "आपका खाता" in results[1][0]
            fresh_alice.post("/account/preferences", {"language": "fr"}, status=422)
            fresh_alice.post("/account/preferences", {"language": "hi", "user_id": "bob"}, status=422)
            fresh_alice.request("/account/preferences", data={"language": "hi"}, status=403)
            fresh_alice.post("/language", {"language": "en", "_return": "//evil.example"}, status=422)
            assert dict(connection.execute("SELECT username,ui_language FROM platform_users")) == {"alice": "en", "bob": "hi"}
            alice.post("/language", {"language": "en", "_return": "/"})
            checks.append("Hindi default, per-session switching, saved profile language, user isolation and unchanged customer text")

            before = connection.execute("SELECT COUNT(*) FROM platform_audit").fetchone()[0]
            for path in (f"/t/{alpha}", f"/t/{alpha}/contacts", f"/t/{alpha}/contacts/{contact}",
                         f"/t/{alpha}/members", f"/t/{alpha}/audit"):
                bob.request(path, status=404)
            bob.post(f"/t/{alpha}/contacts/save", {
                "id": contact, "version": "1", "name": "stolen", "stage": "open"}, status=404)
            bob.post(f"/t/{alpha}/contacts/archive", {
                "id": contact, "version": "1", "archived": "1"}, status=404)
            bob.post(f"/t/{beta}/contacts/save", {
                "id": "", "version": "0", "name": "bad link", "stage": "open", "related_id": company}, status=422)
            assert connection.execute("SELECT COUNT(*) FROM platform_audit").fetchone()[0] == before
            checks.append("tenant isolation for lists, records, writes, audit, members and foreign links")

            update = {"id": contact, "version": "1", "name": "Updated contact", "stage": "active",
                      "related_id": company}
            alice.post(f"/t/{alpha}/contacts/save", update)
            alice.post(f"/t/{alpha}/contacts/save", update, status=409)
            assert connection.execute("SELECT version FROM crm_records WHERE id=?", (contact,)).fetchone()[0] == 2
            alice.post(f"/t/{alpha}/contacts/archive", {"id": contact, "version": "2", "archived": "1"}, status=409)
            alice.post(f"/t/{alpha}/tasks/archive", {"id": task, "version": "1", "archived": "1"})
            alice.post(f"/t/{alpha}/tasks/archive", {"id": task, "version": "1", "archived": "0"}, status=409)
            alice.post(f"/t/{alpha}/tasks/archive", {"id": task, "version": "2", "archived": "0"})
            alice.post(f"/t/{alpha}/tasks/archive", {"id": task, "version": "3", "archived": "1"})
            alice.post(f"/t/{alpha}/deals/archive", {"id": deal, "version": "1", "archived": "1"})
            alice.post(f"/t/{alpha}/contacts/archive", {"id": contact, "version": "2", "archived": "1"})
            alice.post(f"/t/{alpha}/companies/archive", {"id": company, "version": "1", "archived": "1"})
            alice.post(f"/t/{alpha}/contacts/archive", {"id": contact, "version": "3", "archived": "0"}, status=409)
            alice.post(f"/t/{alpha}/companies/archive", {"id": company, "version": "2", "archived": "0"})
            alice.post(f"/t/{alpha}/contacts/archive", {"id": contact, "version": "3", "archived": "0"})
            alice.post(f"/t/{alpha}/deals/archive", {"id": deal, "version": "2", "archived": "0"})
            alice.post(f"/t/{alpha}/tasks/archive", {"id": task, "version": "4", "archived": "0"})
            checks.append("optimistic conflicts, atomic audit, archive/restore and relationship protection")

            alice.post(f"/t/{alpha}/members/save", {"username": "viewer", "role": "viewer", "password": password})
            viewer = Client(first)
            viewer.login("viewer", password)
            viewer.request(f"/t/{alpha}/contacts")
            viewer.post(f"/t/{alpha}/contacts/save", {"id": "", "version": "0", "name": "denied", "stage": "open"}, status=403)
            viewer.request(f"/t/{alpha}/members", status=403)
            alice.post(f"/t/{alpha}/members/save", {"username": "alice", "role": "viewer"}, status=409)
            alice.post(f"/t/{alpha}/members/remove", {"username": "alice", "role": "viewer"}, status=409)
            alice.post(f"/t/{alpha}/members/save", {"username": "viewer", "role": "editor"})
            viewer.create(alpha, "contacts", "Editor can write")
            alice.post(f"/t/{alpha}/members/remove", {"username": "viewer", "role": "viewer"})
            viewer.request(f"/t/{alpha}/contacts", status=404)
            alice.post(f"/t/{alpha}/members/save", {"username": "bob", "role": "owner"})
            _, hdr = alice.post(f"/t/{alpha}/members/save", {"username": "alice", "role": "viewer"})
            assert hdr["Location"] == "/", "Self-demotion must redirect to an accessible page"
            bob.post(f"/t/{alpha}/members/save", {"username": "alice", "role": "owner"})
            alice.post(f"/t/{alpha}/members/remove", {"username": "bob", "role": "viewer"})
            bob.request(f"/t/{beta}/contacts")
            checks.append("owner/editor/viewer roles, immediate membership revocation and last-owner protection")

            before = connection.execute("SELECT COUNT(*) FROM crm_records").fetchone()[0]
            path = f"/t/{alpha}/contacts/save"
            values = {"id": "", "version": "0", "name": "security test", "stage": "open"}
            alice.post(path, {**values, "_csrf": "0" * 64}, status=403)
            alice.request(path, data=values, status=403)
            alice.post(path, values, headers={"Origin": "https://evil.example"}, status=403)
            alice.post(path, values, headers={"Sec-Fetch-Site": "cross-site"}, status=403)
            alice.post(path, values, headers={"X-CSRF-Token": alice.csrf}, status=400)
            encoded = urllib.parse.urlencode({"_csrf": alice.csrf, **values}).encode()
            alice.request(path, raw=encoded + b"&name=duplicate", status=400)
            alice.request(path, raw=encoded + b"&phone=%FF", status=400)
            alice.request(path, raw=encoded + b"&phone=%00", status=400)
            alice.post(path, {**values, "tenant_id": beta}, status=422)
            alice.post(f"/t/{alpha}/tasks/save", {**values, "due_date": "2026-02-30"}, status=422)
            alice.post(path, {**values, "notes": "x" * 4001}, status=422)
            assert connection.execute("SELECT COUNT(*) FROM crm_records").fetchone()[0] == before
            checks.append("CSRF, origin, Fetch Metadata, pollution, UTF-8, NUL, overposting and validation rejection")

            # Large-list fixture tests pagination independently of the create form.
            for number in range(55):
                connection.execute("INSERT INTO crm_records(tenant_id,id,kind,name,email,phone,notes,stage,amount_minor,currency,due_date,version,archived) VALUES (?,?,'contacts',?,'','','','open',0,'USD','',1,FALSE)",
                                   (alpha, "page-" + str(number), f"Pagination {number:03}"))
            connection.commit()
            text, _ = alice.request(f"/t/{alpha}/contacts?q=Pagination")
            assert text.count('<tr>') == 51 and "Pagination 049" in text and "Pagination 050" not in text
            assert "Next" in text
            text, _ = alice.request(f"/t/{alpha}/contacts?q=Pagination&offset=50")
            assert text.count('<tr>') == 6 and "Pagination 054" in text and "Previous" in text
            checks.append("bounded search results and pagination beyond 50 records")

            token = next(c.value for c in alice.cookies if c.name == "bhash-local-session")
            assert not connection.execute("SELECT 1 FROM platform_sessions WHERE token_hash=?", (token,)).fetchone()
            assert connection.execute("SELECT 1 FROM platform_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            second = Server(command, database, provider=provider)
            servers.append(second)
            shared = Client(second, alice.cookies)
            shared.request(f"/t/{alpha}/contacts")
            shared.create(alpha, "tasks", "Written by second worker")

            # Deterministically reproduce a timestamp advanced by a cooperating
            # worker after another request captured its own clock value.
            future_touch = int(time.time() * 1000) + 250
            connection.execute("UPDATE platform_sessions SET touched=? WHERE token_hash=?",
                               (future_touch, hashlib.sha256(token.encode()).hexdigest()))
            connection.commit()
            shared.request(f"/t/{alpha}/contacts")
            assert connection.execute("SELECT touched FROM platform_sessions WHERE token_hash=?",
                                      (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()[0] >= future_touch
            checks.append("concurrent session touches never backdate or falsely reject a live session")

            # Two independent workers try the same optimistic version simultaneously.
            isolated_cookies = http.cookiejar.CookieJar()
            for cookie in alice.cookies:
                isolated_cookies.set_cookie(copy.copy(cookie))
            parallel = Client(second, isolated_cookies)
            parallel.request(f"/t/{alpha}/contacts/{contact}")
            version = connection.execute("SELECT version FROM crm_records WHERE id=?", (contact,)).fetchone()[0]
            barrier = threading.Barrier(2)
            def concurrent_save(client, label):
                barrier.wait(timeout=10)
                try:
                    client.post(f"/t/{alpha}/contacts/save", {
                        "id": contact, "version": str(version), "name": label, "stage": "active"})
                    return 303
                except AssertionError as error:
                    assert error.args[0][1] == 409, error
                    return 409
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(concurrent_save, alice, "First worker edit"),
                           pool.submit(concurrent_save, parallel, "Second worker edit")]
                assert sorted(f.result(timeout=30) for f in futures) == [303, 409]
            assert connection.execute("SELECT version FROM crm_records WHERE id=?", (contact,)).fetchone()[0] == version + 1
            checks.append("simultaneous edits across workers commit exactly one version")
            first.stop()
            shared.request(f"/t/{alpha}/tasks")
            replacement = Server(command, database, provider=provider)
            servers.append(replacement)
            resumed = Client(replacement, alice.cookies)
            resumed.request(f"/t/{alpha}/contacts")
            checks.append("hashed persistent sessions across two processes and restart")

            resumed.post("/logout", {})
            shared.post(f"/t/{alpha}/contacts/save", values, status=403)
            checks.append("logout revokes sessions across workers")

            attacker = Client(second)
            attacker.request("/")
            for _ in range(5):
                attacker.post("/login", {"username": "missing-account", "password": password}, status=401)
            attacker.post("/login", {"username": "missing-account", "password": password}, status=429)
            other = Client(replacement, attacker.cookies)
            other.request("/")
            other.post("/login", {"username": "missing-account", "password": password}, status=429)
            checks.append("shared durable login rate limits")

            # Persisted expiry must be enforced by a different worker as well.
            bob_other = Client(second, bob.cookies)
            bob_other.request("/")
            bob_token = next(c.value for c in bob.cookies if c.name == "bhash-local-session")
            connection.execute("UPDATE platform_sessions SET touched=? WHERE token_hash=?",
                               (int(time.time() * 1000) - 1800001, hashlib.sha256(bob_token.encode()).hexdigest()))
            connection.commit()
            text, _ = bob_other.request("/")
            assert 'action="/login"' in text
            checks.append("persistent idle expiry is enforced across workers")

            changing = Client(second, viewer.cookies)
            changing.request("/account")
            old_cookies = http.cookiejar.CookieJar()
            for cookie in changing.cookies:
                old_cookies.set_cookie(copy.copy(cookie))
            old_csrf = changing.csrf
            new_password = "  Changed-" + secrets.token_hex(10) + "  "
            changing.post("/account/password", {"current_password": "incorrect", "new_password": new_password,
                                                "confirm_password": new_password}, status=401)
            changing.post("/account/password", {"current_password": password, "new_password": new_password,
                                                "confirm_password": "does-not-match"}, status=422)
            changing.post("/account/password", {"current_password": password, "new_password": new_password,
                                                "confirm_password": new_password})
            revoked = Client(replacement, old_cookies)
            revoked.csrf = old_csrf
            revoked.post("/tenants", {"name": "must not be created"}, status=403)
            changing.login("viewer", new_password)
            checks.append("self-service password changes preserve exact input and revoke all sessions")

            # A real server with production policy must set secure host cookies.
            production = Server(command, database, provider=provider, origin="https://crm.example")
            servers.append(production)
            req = urllib.request.Request(production.origin + "/", headers={"Host": "crm.example"})
            with urllib.request.urlopen(req, timeout=10) as response:
                cookie = response.headers["Set-Cookie"]
                assert cookie.startswith("__Host-bhash-session=")
                assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
            checks.append("production host validation and secure cookies")
            for server in servers:
                assert password not in "\n".join(server.logs)
                assert new_password not in "\n".join(server.logs)
                assert token not in "\n".join(server.logs)
            checks.append("credentials and bearer tokens absent from server logs")
        finally:
            for server in servers:
                server.stop()
            connection.close()
    result = {"status": "passed", "checks": checks, "runtime": runtime, "database": provider}
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--jar", type=Path)
    group.add_argument("--clr", type=Path, help="Compiled CLR output directory")
    group.add_argument("--native", type=Path, help="Compiled native executable")
    parser.add_argument("--provider", choices=("sqlite", "postgresql"), default="sqlite")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.jar:
        artifact = args.jar.resolve()
        command, runtime = ["java", "-Dfile.encoding=UTF-8", "-jar", str(artifact)], "JVM"
    elif args.clr:
        artifact = args.clr.resolve() / "BhashProgram.dll"
        command, runtime = ["dotnet", str(artifact)], "CLR"
    else:
        artifact = args.native.resolve()
        command, runtime = [str(artifact)], "native"
    if args.provider == "postgresql":
        # Require an explicit, dedicated test database. Never migrate an existing one.
        with connect_database(None, "postgresql") as connection:
            assert connection.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'").fetchone()[0] == 0, "PostgreSQL test database must be empty"
    verify(command, artifact, args.provider, runtime, args.report)
