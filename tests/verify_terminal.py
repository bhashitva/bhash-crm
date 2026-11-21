"""Verify the actual launcher emits Hindi as UTF-8 on stdout and stderr."""
from pathlib import Path
import subprocess


launcher = Path("StartCrm.java")
result = subprocess.run(["java", "-Dstdout.encoding=IBM437", "-Dstderr.encoding=IBM437",
                         str(launcher), "--terminal-check"], capture_output=True, timeout=30)
assert result.returncode == 0, "Terminal check must not require an account or a database"
assert result.stdout.decode("utf-8").strip() == "हिन्दी पाठ ठीक है।"
assert result.stderr.decode("utf-8").strip() == "हिन्दी त्रुटि संदेश ठीक है।"
print("PASS: launcher stdout/stderr remain correct UTF-8 with legacy startup stream encodings")
