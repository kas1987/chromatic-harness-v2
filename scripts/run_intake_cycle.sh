#!/usr/bin/env bash
# Poll inbox -> auto_intake with JSONL audit log.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/07_LOGS_AND_AUDIT/intake_cycle"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cycle_$(date -u +%Y%m%d).jsonl"
LIMIT="${CHROMATIC_INTAKE_LIMIT:-10}"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

POLL_OUT="$(mktemp)"
INTAKE_OUT="$(mktemp)"
trap 'rm -f "$POLL_OUT" "$INTAKE_OUT"' EXIT

set +e
python scripts/poll_inbox.py --limit "$LIMIT" >"$POLL_OUT" 2>&1
POLL_EXIT=$?
python scripts/auto_intake.py --limit "$LIMIT" >"$INTAKE_OUT" 2>&1
INTAKE_EXIT=$?
set -e

python - "$LOG_FILE" "$STARTED" "$POLL_EXIT" "$INTAKE_EXIT" "$LIMIT" "$POLL_OUT" "$INTAKE_OUT" <<'PY'
import json, sys
from datetime import datetime, timezone

log_file, started, poll_exit, intake_exit, limit, poll_path, intake_path = sys.argv[1:8]
poll_exit, intake_exit, limit = int(poll_exit), int(intake_exit), int(limit)
poll_raw = open(poll_path, encoding="utf-8").read().strip()
intake_raw = open(intake_path, encoding="utf-8").read().strip()

def try_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw

record = {
    "started_at": started,
    "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "poll_exit": poll_exit,
    "intake_exit": intake_exit,
    "limit": limit,
    "poll_report": try_json(poll_raw),
    "intake_report": try_json(intake_raw),
}
line = json.dumps(record, separators=(",", ":"))
with open(log_file, "a", encoding="utf-8") as f:
    f.write(line + "\n")
print(line)
PY

if [[ "$POLL_EXIT" -ne 0 || "$INTAKE_EXIT" -ne 0 ]]; then
  exit 1
fi
