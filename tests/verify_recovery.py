"""Exercise actual Bhash password recovery with a loopback mail double."""
import argparse
import concurrent.futures
from contextlib import ExitStack, closing
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import tempfile
import threading
from verify import Server, Client, Inputs
from source_checks import SourceDocument


def verify(command, artifact):
    messages, state = [], {'failure': False}
    class Mail(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            assert self.path == '/emails'
            assert self.headers['Authorization'] == 'Bearer recovery-mail-test'
            assert self.headers['Idempotency-Key'].startswith('crm-reset-')
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body['from'] == 'info@bhashitva.org'
            if not state['failure']: messages.append(body)
            self.send_response(503 if state['failure'] else 200)
            self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({'id': secrets.token_hex(12)}).encode())
    mail = ThreadingHTTPServer(('127.0.0.1', 0), Mail)
    threading.Thread(target=mail.serve_forever, daemon=True).start()
    previous = os.environ.copy()
    os.environ.update(CRM_SIGNUP_ENABLED='false', CRM_TURNSTILE_SITE_KEY='', CRM_TURNSTILE_SECRET_KEY='',
                      CRM_RESEND_API_KEY='recovery-mail-test', CRM_MAIL_FROM='info@bhashitva.org')
    servers = []
    try:
        with ExitStack() as cleanup:
            folder = cleanup.enter_context(tempfile.TemporaryDirectory(prefix='crm-recovery-', dir=artifact.parent))
            cleanup.callback(lambda: [server.stop() for server in servers])
            database = Path(folder) / 'crm.db'
            password = '  Original-' + secrets.token_hex(12) + '  '
            new_password = '  नवीन-' + secrets.token_hex(12) + '  '
            for name in ('मनोज श्रीवास्तव', 'bob', 'legacy'):
                result = subprocess.run([*command, f'--db={database}', '--bootstrap=true'],
                    env={**os.environ, 'BHASH_CRM_USER': name, 'BHASH_CRM_PASSWORD': password, 'BHASH_CRM_TENANT': name},
                    capture_output=True, timeout=40)
                assert result.returncode == 0, result.stderr
            def sql(query, args=()):
                with closing(sqlite3.connect(database)) as connection:
                    rows = connection.execute(query, args).fetchall(); connection.commit(); return rows
            sql('UPDATE platform_users SET email=?,email_verified=TRUE,ui_language=? WHERE username=?', ('owner@example.org','en','मनोज श्रीवास्तव'))
            sql('UPDATE platform_users SET email=?,email_verified=TRUE WHERE username=?', ('bob@example.org','bob'))
            original = sql('SELECT username,password_hash FROM platform_users ORDER BY username')
            command = [*command, f'--signup-test-api=http://127.0.0.1:{mail.server_port}']
            first, second = Server(command, database), Server(command, database)
            servers.extend((first, second))
            one, two, other = Client(first), Client(second), Client(second)
            one.login('मनोज श्रीवास्तव', password, language=None)
            two.login('मनोज श्रीवास्तव', password, language=None)
            other.login('bob', password, language=None)
            def visitor(server=None):
                client = Client(server or first); client.request('/forgot-password'); return client
            def request(email):
                client = visitor(); page, _ = client.post('/forgot-password', {'email': email}, status=200); return page
            def link():
                return re.search(r'/reset-password\?token=[a-f0-9]{64}', messages[-1]['text']).group()
            page, _ = Client(first).request('/')
            assert 'href="/forgot-password"' in page and 'कूटशब्द भूल गए?' in page
            assert 'href="/signup"' not in page, 'Recovery must work independently of public signup'
            for key in ('forgot', 'reset'):
                SourceDocument(Client(first).request('/source/'+key+'?language=hi')[0]).check()
            invalid = visitor()
            invalid.request('/forgot-password', data={'email':'owner@example.org'}, status=403)
            invalid.post('/forgot-password', {'email':'owner@example.org'}, headers={'Origin':'https://evil.example'}, status=403)
            invalid.post('/forgot-password', {'email':'owner@example.org','user_id':'bob'}, status=422)
            invalid.post('/forgot-password', {'email':'invalid'}, status=422)
            unknown = request('missing@example.org'); assert not messages
            known = request('OWNER@EXAMPLE.ORG'); assert known == unknown
            assert messages[-1]['to'] == ['owner@example.org']
            assert messages[-1]['subject'] == 'Reset your Bhash CRM password'
            old_path = link(); token = old_path.split('=')[1]
            row = sql('SELECT token_hash,credential_stamp,sent FROM crm_password_resets')[0]
            assert row[0] == hashlib.sha256(token.encode()).hexdigest() and row[2] == 1
            assert token not in known and new_password not in known
            assert sql('SELECT username,password_hash FROM platform_users ORDER BY username') == original
            scanner = Client(second)
            for _ in range(2):
                form, headers = scanner.request(old_path)
                assert headers['Content-Language'] == 'en' and headers['Referrer-Policy'] == 'strict-origin'
                assert '<script' not in form and headers['Cache-Control'] == 'no-store'
            assert sql('SELECT COUNT(*) FROM crm_password_resets') == [(1,)]
            # Requesting another link does not let an attacker invalidate the first one.
            request('owner@example.org'); new_path = link()
            assert new_path != old_path
            scanner.request(old_path)
            values = dict(token=token, password=new_password, confirm_password=new_password)
            scanner.post('/reset-password', {**values,'_csrf':''}, status=403)
            scanner.post('/reset-password', {**values,'confirm_password':'different'}, status=422)
            scanner.post('/reset-password', {**values,'email':'bob@example.org'}, status=422)
            scanner.post('/reset-password', {**values,'password':'short','confirm_password':'short'}, status=422)
            scanner.request('/reset-password?token=bad', status=422)
            scanner.request(old_path+'&token=extra', status=422)
            finishers = [Client(first), Client(second)]
            for client in finishers: client.request(old_path)
            def finish(client):
                try:
                    text, _ = client.post('/reset-password', values, status=200)
                    assert 'Password updated' in text
                    return 'updated'
                except AssertionError as error:
                    assert error.args[0][1] == 422, error
                    return 'used'
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                assert sorted(pool.map(finish, finishers)) == ['updated','used']
            assert sql('SELECT COUNT(*) FROM crm_password_resets') == [(0,)]
            for client in (one, two):
                signed_out, _ = client.request('/'); assert 'action="/login"' in signed_out
            other.request('/account')  # Another user's sessions and password remain intact.
            Client(first).request(new_path, status=422)
            sign_in = Client(first); sign_in.request('/')
            sign_in.post('/login', {'username':'मनोज श्रीवास्तव','password':password}, status=401)
            sign_in.login('मनोज श्रीवास्तव', new_password, language=None)
            # Changing a password through Account also invalidates previously issued links.
            sql('DELETE FROM crm_signup_limits')
            request('owner@example.org'); stale = link()
            sign_in.post('/account/password', {'current_password':new_password,'new_password':password,'confirm_password':password})
            Client(first).request(stale, status=422)
            # Expired, unsent, future-dated, changed-email, inactive and unverified links cannot reset.
            for mutation in ("expires=0", "sent=FALSE", "created=created+86400000"):
                sql('DELETE FROM crm_signup_limits'); request('owner@example.org'); path = link()
                sql('UPDATE crm_password_resets SET '+mutation)
                Client(first).request(path, status=422)
            for mutation, undo in (("active=FALSE","active=TRUE"), ("email_verified=FALSE","email_verified=TRUE"),
                                   ("email='changed@example.org'","email='owner@example.org'")):
                sql('DELETE FROM crm_signup_limits'); request('owner@example.org'); path = link()
                sql('UPDATE platform_users SET '+mutation+' WHERE username=?', ('मनोज श्रीवास्तव',))
                Client(first).request(path, status=422)
                sql('UPDATE platform_users SET '+undo+' WHERE username=?', ('मनोज श्रीवास्तव',))
            # Delivery failure has the same public response and leaves no usable token.
            sql('DELETE FROM crm_signup_limits'); sql('DELETE FROM crm_password_resets')
            state['failure'] = True
            assert request('owner@example.org') == unknown
            assert sql('SELECT COUNT(*) FROM crm_password_resets') == [(0,)]
            state['failure'] = False
            sql("UPDATE platform_users SET email='legacy@example.org' WHERE username='legacy'")
            count = len(messages); assert request('legacy@example.org') == unknown; assert len(messages) == count
            # All mail, including recovery and signup, shares the same durable provider budget.
            sql('DELETE FROM crm_signup_limits'); request('bob@example.org')
            assert 'कूटशब्द' in messages[-1]['subject']
            budget = hashlib.sha256(b'mail-budget').hexdigest()
            sql('UPDATE crm_signup_limits SET attempts=80 WHERE key_hash=?', (budget,))
            count = len(messages); assert request('owner@example.org') == unknown; assert len(messages) == count
            sql('DELETE FROM crm_signup_limits')
            for _ in range(3): request('missing@example.org')
            first.stop(); first = Server(command, database); servers.append(first)
            limited = visitor(); limited.post('/forgot-password', {'email':'missing@example.org'}, status=429)
            for server in servers:
                assert all(value not in '\n'.join(server.logs) for value in (token, password, new_password, 'recovery-mail-test'))
            assert sql('PRAGMA quick_check') == [('ok',)]
            assert sql("SELECT password_hash FROM platform_users WHERE username='bob'")[0][0] == dict(original)['bob']
            print('PASS: email recovery, bilingual forms/mail, generic responses, single-use racing links, expiry, CSRF, exact passwords, cross-worker session revocation, stale-link invalidation, durable shared limits and unchanged other accounts')
    finally:
        for server in servers: server.stop()
        mail.shutdown(); mail.server_close()
        os.environ.clear(); os.environ.update(previous)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--jar', type=Path); group.add_argument('--clr', type=Path)
    args = parser.parse_args(); artifact = (args.jar or args.clr).resolve()
    command = ['java','-Dfile.encoding=UTF-8','-jar',str(artifact)] if args.jar else ['dotnet',str(artifact/'BhashProgram.dll')]
    verify(command, artifact)
