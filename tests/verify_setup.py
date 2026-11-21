"""Regression check for password rejection followed by setup retry; disposable data only."""
import os
from contextlib import closing
from pathlib import Path
import secrets
import sqlite3
import subprocess
import tempfile


def main():
    jar = Path("target/crm.jar").resolve()
    with tempfile.TemporaryDirectory(prefix="crm-setup-test-", dir=jar.parent) as folder:
        database = Path(folder) / "crm.db"
        command = ["java", "-Dfile.encoding=UTF-8", "-jar", str(jar), f"--db={database}"]

        def run(option, password=None):
            env = dict(os.environ)
            env.update(BHASH_CRM_USER="setup-test", BHASH_CRM_TENANT="Disposable setup test")
            if password is not None:
                env["BHASH_CRM_PASSWORD"] = password
            return subprocess.run([*command, option], env=env, capture_output=True,
                                  text=True, encoding="utf-8", timeout=30)

        assert run("--setup-status=true").stdout.strip() == "SETUP_REQUIRED"
        assert database.exists(), "Fixture must reproduce an existing schema-only database"
        rejected = run("--bootstrap=true", "short")
        assert rejected.returncode != 0
        assert run("--setup-status=true").stdout.strip() == "SETUP_REQUIRED"
        accepted = run("--bootstrap=true", "Test-" + secrets.token_hex(12))
        assert accepted.returncode == 0, "Valid retry must create the account"
        assert run("--setup-status=true").stdout.strip() == "SETUP_READY"
        assert run("--bootstrap=true", "short").returncode != 0
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute("SELECT COUNT(*) FROM platform_users").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM platform_tenants").fetchone()[0] == 1
        print("PASS: failed setup can be retried; successful account remains intact")


if __name__ == "__main__":
    main()
