import shutil
import subprocess
import sys


def _find_bd():
    for name in ("bd.cmd", "bd.exe", "bd"):
        found = shutil.which(name)
        if found:
            return found
    return None


BD = _find_bd()
if BD is None:
    sys.exit(0)  # fail-open: bd not installed, skip sweep

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

try:
    subprocess.run(
        [BD, "close"] + ids + ["--reason", "session-end sweep", "--quiet"],
        check=False,
        shell=False,
    )
except Exception:
    pass  # fail-open: bd failure must never break SessionEnd
