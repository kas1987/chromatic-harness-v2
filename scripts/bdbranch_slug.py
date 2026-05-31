"""Given a bead ID on argv[1], print a git-safe slug for branch naming."""

import sys
import json
import re
import subprocess

bead_id = sys.argv[1]
bd_cmd = r"C:\Users\kas41\AppData\Roaming\npm\bd.cmd"
result = subprocess.run(
    [bd_cmd, "show", bead_id, "--json"], capture_output=True, text=True
)
if result.returncode != 0 or not result.stdout.strip():
    sys.exit(1)

data = json.loads(result.stdout)
title = data[0]["title"] if isinstance(data, list) else data["title"]
slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).lower().strip("-")[:40]
print(slug)
