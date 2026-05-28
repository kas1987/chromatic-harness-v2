#!/usr/bin/env bash
# review-daemon-startup.sh — SessionStart hook
# Checks if review-daemon dist is built; writes status JSON.
# Pattern follows multica-startup.sh. Always exits 0 (fail-open).

set -euo pipefail

STATUS_FILE="${HOME}/.claude/.agents/router/review-daemon-status.json"
DAEMON_DIST="${HOME}/.claude/review-daemon/dist/index.js"
mkdir -p "$(dirname "$STATUS_FILE")"

write_status() {
  local up="$1" reason="$2"
  jq -cn \
    --argjson up "$up" \
    --arg reason "$reason" \
    --arg checked_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{up: $up, checked_at: $checked_at, reason: $reason}' \
    > "$STATUS_FILE" 2>/dev/null || true
}

# Check if dist is built
if [ ! -f "$DAEMON_DIST" ]; then
  write_status false "dist/index.js not found — run npm run build in ~/.claude/review-daemon"
  exit 0
fi

# Check node is available
if ! command -v node &>/dev/null; then
  write_status false "node not found on PATH"
  exit 0
fi

write_status true "review-daemon dist present and node available"
exit 0
