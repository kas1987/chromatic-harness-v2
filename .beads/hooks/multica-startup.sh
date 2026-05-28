#!/usr/bin/env bash
# multica-startup.sh — SessionStart hook: ensures Multica daemon is running.
# Follows ollama-liveness.sh pattern. Always exits 0 (fail-open).
set -u

STATUS_DIR="${HOME}/.claude/.agents/router"
STATUS_FILE="${STATUS_DIR}/multica-status.json"
MULTICA_BIN="${MULTICA_BIN:-$HOME/.multica/bin/multica}"
mkdir -p "${STATUS_DIR}" 2>/dev/null

ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Resolve binary
if ! [ -f "$MULTICA_BIN" ] && ! command -v multica &>/dev/null; then
  jq -cn --arg ts "$ts" '{up:false,checked_at:$ts,reason:"not_installed"}' \
    > "$STATUS_FILE" 2>/dev/null || true
  exit 0
fi

MCMD="$MULTICA_BIN"
[ ! -f "$MCMD" ] && MCMD="multica"

# Probe current status
status_out=$("$MCMD" daemon status 2>/dev/null || true)

if echo "$status_out" | grep -q "running"; then
  pid=$(echo "$status_out" | grep -oE 'pid [0-9]+' | grep -oE '[0-9]+' || echo "")
  jq -cn --arg ts "$ts" --arg pid "$pid" \
    '{up:true,checked_at:$ts,auto_started:false,pid:$pid,reason:null}' \
    > "$STATUS_FILE" 2>/dev/null || true
  exit 0
fi

# Not running — auto-start
"$MCMD" daemon start 2>/dev/null || true
sleep 2

# Re-probe
status_out2=$("$MCMD" daemon status 2>/dev/null || true)
if echo "$status_out2" | grep -q "running"; then
  pid=$(echo "$status_out2" | grep -oE 'pid [0-9]+' | grep -oE '[0-9]+' || echo "")
  jq -cn --arg ts "$ts" --arg pid "$pid" \
    '{up:true,checked_at:$ts,auto_started:true,pid:$pid,reason:null}' \
    > "$STATUS_FILE" 2>/dev/null || true
else
  jq -cn --arg ts "$ts" \
    '{up:false,checked_at:$ts,auto_started:true,reason:"start_failed"}' \
    > "$STATUS_FILE" 2>/dev/null || true
fi

exit 0
