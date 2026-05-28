#!/usr/bin/env bash
# harness-log-rotate.sh — Self-maintaining log rotation for harness data files
# Prevents unbounded growth of JSONL logs that cause agent-watch to hang.
# Run as SessionStart hook (fast, <1s).
# Safety: always exits 0, never blocks session.
set -u

LOG_LINE_CAP="${HARNESS_LOG_CAP:-200}"

rotate_log() {
  local file="$1"
  local cap="${2:-$LOG_LINE_CAP}"
  [ -f "$file" ] || return 0
  local lines
  lines=$(wc -l < "$file" 2>/dev/null || echo 0)
  [ "$lines" -le "$cap" ] && return 0
  # Archive and trim
  local archive="${file}.$(date +%Y%m%d).bak"
  [ -f "$archive" ] || cp "$file" "$archive" 2>/dev/null || true
  tail -"$cap" "$file" > "${file}.tmp" 2>/dev/null && mv "${file}.tmp" "$file" 2>/dev/null || rm -f "${file}.tmp" 2>/dev/null
}

# Rotate router logs
rotate_log "${HOME}/.claude/.agents/router/log.jsonl" "$LOG_LINE_CAP"
rotate_log "${HOME}/.claude/.agents/router/dispatch.jsonl" "$LOG_LINE_CAP"

# Rotate intake queue (higher cap since items have state)
rotate_log "${HOME}/.claude/.agents/intake/queue.jsonl" 500
rotate_log "${HOME}/.claude/.agents/intake/dispatch.jsonl" "$LOG_LINE_CAP"

# Rotate circuit-breaker archives (keep 1 week)
find "${HOME}/.claude/.agents/router" -name '*.bak' -mtime +7 -delete 2>/dev/null || true
find "${HOME}/.claude/.agents/intake" -name 'queue-archive-*' -mtime +7 -delete 2>/dev/null || true

exit 0