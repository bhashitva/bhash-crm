"""Exercise Bhash signup with explicit loopback provider doubles; never sends mail."""
import argparse
from contextlib import ExitStack, closing
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from verify import Server, Client, Inputs
from source_checks import SourcePanel, SourceDocument


def verify(command, artifact):
    proofs, messages = {}, []
    state = {"mail_failure": False}

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            code, response = 200, {}
            if self.path == '/turnstile':
                assert data['secret'] == 'private-captcha-test'
                response = proofs.get(data['response'], {'success': False})
                if response == 'unavailable':
                    code, response = 503, {}
                elif response == 'malformed':
                    response = []
            elif self.path == '/emails':
                assert self.headers['Authorization'] == 'Bearer private-mail-test'
                assert self.headers['Idempotency-Key'].startswith('crm-verify-')
                assert data['from'] == 'info@bhashitva.org'
                if state['mail_failure']:
                    code = 503
                else:
                    messages.append(data)
                    response = {'id': secrets.token_hex(12)}
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    endpoint = f'http://127.0.0.1:{provider.server_port}'
    saved = os.environ.copy()
    os.environ.update(CRM_SIGNUP_ENABLED='true', CRM_TURNSTILE_SITE_KEY='public-test-site',
                      CRM_TURNSTILE_SECRET_KEY='private-captcha-test', CRM_RESEND_API_KEY='private-mail-test',
                      CRM_MAIL_FROM='info@bhashitva.org', CRM_SIGNUP_HOST='bhashcrm.bhashitva.org')
    servers = []
    try:
        with ExitStack() as cleanup:
            folder = cleanup.enter_context(tempfile.TemporaryDirectory(prefix='crm-signup-', dir=artifact.parent))
            cleanup.callback(lambda: [s.stop() for s in servers])
            database = Path(folder) / 'signup.db'
            password = '  Test-' + secrets.token_hex(12) + '  '
            result = subprocess.run([*command, f'--db={database}', '--bootstrap=true'],
                                    env={**os.environ, 'BHASH_CRM_USER': 'legacy-owner',
                                         'BHASH_CRM_PASSWORD': password, 'BHASH_CRM_TENANT': 'Existing'},
                                    capture_output=True, timeout=40)
            assert result.returncode == 0, result.stderr
            command = [*command, f'--signup-test-api={endpoint}']
            server = Server(command, database)
            servers.append(server)

            def db(sql, values=()):
                with closing(sqlite3.connect(database)) as conn:
                    rows = conn.execute(sql, values).fetchall()
                    conn.commit()
                    return rows

            old_hash = db('SELECT password_hash FROM platform_users')[0][0]
            existing_tenant = db('SELECT id FROM platform_tenants')[0][0]

            def visitor():
                client = Client(server)
                page, headers = client.request('/signup')
                assert headers['Content-Language'] == 'hi'
                assert 'challenges.cloudflare.com' in headers['Content-Security-Policy']
                assert 'name="password"' not in page
                return client

            def proof(client, **changes):
                token = secrets.token_hex(20)
                page, _ = client.request('/signup')
                cdata = re.search(r'data-cdata="([a-f0-9]+)"', page).group(1)
                proofs[token] = dict(success=True, hostname='bhashcrm.bhashitva.org',
                                     action='crm-signup', cdata=cdata)
                proofs[token].update(changes)
                return token

            def signup(client, email, token=None, status=200):
                return client.post('/signup', {'email': email, 'cf-turnstile-response': token or proof(client)}, status=status)

            def link():
                return re.search(r'(/verify-email\?token=[a-f0-9]{64})', messages[-1]['text']).group(1)

            client = visitor()
            for page_key in ('signup', 'verify'):
                document = SourceDocument(client.request('/source/' + page_key + '?language=hi')[0]).check()
                assert all('private-captcha-test' not in code and 'private-mail-test' not in code for code in document.codes)
                shared = SourceDocument(client.request('/source/' + page_key + '/signup?language=en')[0]).check()
                assert shared.codes == [(Path(__file__).resolve().parents[1] / 'src/signup.bhash').read_text(encoding='utf-8')]
            signup(client, 'invalid-address', status=422)
            client.post('/signup', {'email': 'ok@example.org', 'cf-turnstile-response': '', 'role': 'owner'}, status=422)
            signup(client, 'no-check@example.org', token='missing', status=422)
            for changes in ({'hostname': 'evil.example'}, {'action': 'login'}, {'cdata': 'wrong'}):
                bad = visitor()
                signup(bad, secrets.token_hex(4) + '@example.org', proof(bad, **changes), status=422)
            unavailable = visitor()
            token = proof(unavailable)
            proofs[token] = 'unavailable'
            signup(unavailable, 'unavailable@example.org', token, status=503)
            assert not messages and db('SELECT COUNT(*) FROM platform_users')[0][0] == 1

            client = visitor()
            token = proof(client)
            text, _ = signup(client, 'New.Owner@Example.org', token)
            assert len(messages) == 1 and messages[-1]['to'] == ['new.owner@example.org']
            assert '30' in messages[-1]['text'] or '३०' in messages[-1]['text']
            path = link()
            raw_token = path.split('=')[1]
            assert raw_token not in text and db('SELECT COUNT(*) FROM platform_users')[0][0] == 1
            assert db('SELECT token_hash,email,sent FROM crm_email_verifications') == [
                (hashlib.sha256(raw_token.encode()).hexdigest(), 'new.owner@example.org', 1)]
            signup(client, 'replay@example.org', token, status=422)
            assert len(messages) == 1

            # Mail scanner GETs are harmless; the link can be completed in another browser.
            finisher = Client(server)
            page, headers = finisher.request(path)
            assert headers['Referrer-Policy'] == 'strict-origin' and '<script' not in page
            finisher.request(path)
            assert db('SELECT COUNT(*) FROM platform_users')[0][0] == 1
            values = dict(token=raw_token, username='फ़ैज़ श्रीवास्तव १२', password=password,
                          confirm_password=password, organization='नई संस्था')
            finisher.post('/verify-email', {**values, 'confirm_password': 'different'}, status=422)
            finisher.post('/verify-email', {**values, 'tenant_id': existing_tenant}, status=422)
            finisher.post('/verify-email', {**values, 'password': 'short', 'confirm_password': 'short'}, status=422)
            for invalid_name in ('िमनोज', 'मनोज\u200b', '<मनोज>'):
                finisher.post('/verify-email', {**values, 'username': invalid_name}, status=422)
            old_csrf = finisher.csrf
            finisher.post('/verify-email', values)
            page, _ = finisher.request('/')
            assert finisher.csrf != old_csrf
            assert db('SELECT email,email_verified,ui_language FROM platform_users WHERE username=?', ('फ़ैज़ श्रीवास्तव १२',)) == [
                ('new.owner@example.org', 1, 'hi')]
            new_tenant = db('SELECT tenant_id FROM platform_members m JOIN platform_users u ON m.user_id=u.id WHERE u.username=?', ('फ़ैज़ श्रीवास्तव १२',))[0][0]
            assert db('SELECT name FROM platform_tenants WHERE id=?', (new_tenant,)) == [('नई संस्था',)]
            assert new_tenant != existing_tenant
            assert db('SELECT role FROM platform_members WHERE tenant_id=?', (new_tenant,)) == [('owner',)]
            assert not db('SELECT * FROM crm_email_verifications')
            finisher.request(f'/t/{existing_tenant}/contacts', status=404)
            fresh = Client(server)
            fresh.request(path, status=422)
            fresh.login('फ़ैज़  श्रीवास्तव १२', password, language=None)
            fresh.request(f'/t/{new_tenant}/contacts')
            shaped = Client(server)
            shaped.login('फ़ैज़ श्\u200dरीवास्तव १२', password, language=None)
            shaped.request(f'/t/{new_tenant}/contacts')
            old = Client(server)
            old.login('legacy-owner', password)
            assert db('SELECT password_hash,email,email_verified FROM platform_users WHERE username=?', ('legacy-owner',)) == [(old_hash, None, 0)]

            duplicate = visitor()
            duplicate_text, _ = signup(duplicate, 'NEW.OWNER@example.org')
            assert duplicate_text == text, 'Existing email must receive the same non-enumerating response'
            assert len(messages) == 1
            # Failed delivery removes the unusable pending token and never creates an account.
            failure = visitor()
            state['mail_failure'] = True
            signup(failure, 'failed@example.org', status=503)
            state['mail_failure'] = False
            assert not db('SELECT * FROM crm_email_verifications WHERE email=?', ('failed@example.org',))

            expiring = visitor()
            signup(expiring, 'expired@example.org')
            expired_path = link()
            db('UPDATE crm_email_verifications SET expires=0 WHERE email=?', ('expired@example.org',))
            Client(server).request(expired_path, status=422)
            Client(server).request('/verify-email?token=bad', status=422)
            Client(server).request(path + '&token=duplicate', status=422)

            # Two browsers racing one link can create only one user and organization.
            signup(visitor(), 'race@example.org')
            race_path = link()
            racers = [Client(server), Client(server)]
            for racer in racers:
                racer.request(race_path)
            race_values = dict(token=race_path.split('=')[1], username='क' * 64, password=password,
                               confirm_password=password, organization='Race organization')
            racers[0].post('/verify-email', {**race_values, 'username': 'क' * 65}, status=422)
            def finish(racer):
                try:
                    racer.post('/verify-email', race_values)
                    return 'created'
                except AssertionError as error:
                    assert error.args[0][1] in (409, 422), error
                    return 'consumed'
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                assert sorted(pool.map(finish, racers)) == ['consumed', 'created']
            assert db('SELECT COUNT(*) FROM platform_users WHERE email=?', ('race@example.org',)) == [(1,)]
            assert db('SELECT COUNT(*) FROM platform_tenants WHERE name=?', ('Race organization',)) == [(1,)]
            long_name = Client(server)
            long_name.login('क' * 64, password, language=None)

            # Durable per-email quota cannot be reset with a different cookie or server restart.
            for _ in range(3):
                signup(visitor(), 'limited@example.org')
            server.stop()
            server = Server(command, database)
            servers.append(server)
            signup(visitor(), 'limited@example.org', status=429)
            # Global provider budget is checked under the shared SQL lock.
            budget = hashlib.sha256(b'mail-budget').hexdigest()
            db('UPDATE crm_signup_limits SET attempts=80 WHERE key_hash=?', (budget,))
            signup(visitor(), 'over-budget@example.org', status=429)
            assert not db('SELECT * FROM crm_email_verifications WHERE email=?', ('over-budget@example.org',))
            for running in servers:
                logs = '\n'.join(running.logs)
                assert all(secret not in logs for secret in (raw_token, password, 'private-mail-test', 'private-captcha-test'))
            assert db('PRAGMA quick_check') == [('ok',)]
            rejected = subprocess.run([*command, f'--db={database}', '--origin=https://bhashcrm.bhashitva.org', '--port=0'],
                                      capture_output=True, timeout=30)
            assert rejected.returncode != 0 and b'READY ' not in rejected.stdout
            print('PASS: Hindi full names, nukta equivalence, 64-character bounds, Hindi organizations, CAPTCHA binding/replay, verified signup, atomic tenancy, existing accounts, expiry, fail-closed providers, persistent quotas and secret-free logs')
    except Exception:
        for running in servers:
            print('Signup server diagnostics:', ascii('\n'.join(running.logs[-12:])))
        raise
    finally:
        for server in servers:
            server.stop()
        provider.shutdown()
        provider.server_close()
        os.environ.clear()
        os.environ.update(saved)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--jar', type=Path)
    group.add_argument('--clr', type=Path)
    args = parser.parse_args()
    artifact = (args.jar or args.clr).resolve()
    command = ['java', '-Dfile.encoding=UTF-8', '-jar', str(artifact)] if args.jar else ['dotnet', str(artifact / 'BhashProgram.dll')]
    verify(command, artifact)
