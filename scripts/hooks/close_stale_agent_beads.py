import shutil
import subprocess
import sys

# Resolve bd from PATH; fall back to common Windows npm install location
BD = (
    shutil.which("bd")
    or shutil.which("bd.cmd")
    or r"C:\Users\kas41\AppData\Roaming\npm\bd.cmd"
)
if not BD:
    sys.exit(0)  # bd not installed — skip silently rather than break session closeout

result = subprocess.run(
    [BD, "list", "--status", "in_progress", "--limit", "0"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    shell=False,
)

ids = [
    line.strip().split()[1]
    for line in result.stdout.splitlines()
    if "[agent]" in line and len(line.strip().split()) >= 2
]

if not ids:
    sys.exit(0)

subprocess.run(
    [BD, "close"] + ids + ["--reason", "session-end sweep", "--quiet"],
    check=False,
    shell=False,
)
