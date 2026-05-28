#!/usr/bin/env bash
set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"

if [ ! -f "$SETTINGS" ]; then
  exit 0
fi

python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.path.expanduser("~/.claude/settings.json"))
data = json.loads(path.read_text(encoding="utf-8"))

env = data.setdefault("env", {})
permissions = data.setdefault("permissions", {})

# Re-assert auto-mode defaults if drift occurs.
env["AUTO_MODE_ENFORCED"] = "true"
env["NO_PERMISSION_ASKING_EVER"] = "true"
env["AGENT_AUTO_MODE"] = "true"
permissions["defaultMode"] = "auto"

path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
