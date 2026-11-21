"""Upgrade an actual schema-v2 fixture and verify account/data preservation."""
from contextlib import closing
import importlib.util
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("crm_verify", root / "tests/verify.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
with tempfile.TemporaryDirectory(prefix="crm-migration-", dir=root / "target") as folder:
    database = Path(folder) / "legacy.db"
    password = "Test-" + secrets.token_hex(12)
    command = ["java", "-Dfile.encoding=UTF-8", "-jar", str(root / "target/crm.jar")]
    old = subprocess.run(["java", "-jar", str(root / "target/legacy-setup.jar"), f"--db={database}"],
                         env={**os.environ, "BHASH_CRM_PASSWORD": password}, capture_output=True, timeout=30)
    assert old.returncode == 0, "Schema-v2 fixture must be created successfully"
    with closing(sqlite3.connect(database)) as connection:
        previous_hash = connection.execute("SELECT password_hash FROM platform_users").fetchone()[0]
        assert "ui_language" not in [r[1] for r in connection.execute("PRAGMA table_info(platform_users)")]
    upgraded = subprocess.run([*command, f"--db={database}", "--setup-status=true"], capture_output=True, timeout=30)
    assert upgraded.returncode == 0 and upgraded.stdout.strip() == b"SETUP_READY"
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT password_hash,ui_language FROM platform_users").fetchone() == (previous_hash, "hi")
        assert connection.execute("SELECT name,notes FROM crm_records").fetchone() == ("पुरानी कंपनी", "Preserve customer data")
        assert connection.execute("SELECT COUNT(*) FROM platform_members").fetchone()[0] == 1
    server = helpers.Server(command, database)
    try:
        client = helpers.Client(server)
        client.login("legacy-owner", password, language=None)
        text, headers = client.request("/t/legacy-tenant/companies")
        assert headers["Content-Language"] == "hi" and "पुरानी कंपनी" in text
    finally:
        server.stop()
print("PASS: schema-v2 accounts, password hashes, memberships and customer data survive the language migration")
