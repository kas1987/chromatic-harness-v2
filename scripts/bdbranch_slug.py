"""Given a bead ID on argv[1], print a git-safe slug for branch naming."""

import json
import re
import shutil
import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: bdbranch_slug.py <bead-id>", file=sys.stderr)
    sys.exit(1)

bead_id = sys.argv[1]

bd_cmd = shutil.which("bd.cmd") or shutil.which("bd.exe") or shutil.which("bd")
if not bd_cmd:
    print("bd not found in PATH", file=sys.stderr)
    sys.exit(1)

result = subprocess.run(
    [bd_cmd, "show", bead_id, "--json"], capture_output=True, text=True
)
if result.returncode != 0 or not result.stdout.strip():
    sys.exit(1)

try:
    data = json.loads(result.stdout)
except json.JSONDecodeError:
    sys.exit(1)

title = data[0]["title"] if isinstance(data, list) else data["title"]
slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).lower().strip("-")[:40]
print(slug)
