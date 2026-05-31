import subprocess
import sys

BD = r"C:\Users\kas41\AppData\Roaming\npm\bd.cmd"

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
