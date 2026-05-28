#!/usr/bin/env bash
# context-guard.sh — context window warnings + auto-compact at 70%
# 60-70%: yellow warning banner
# >=70%:  red banner + spawns auto-enter-sender.ps1 to fire /compact automatically
#
# Thresholds (override via env):
#   CLAUDE_CONTEXT_LIMIT    default 200000 tokens
#   CONTEXT_WARN_PCT        default 60
#   CONTEXT_CRITICAL_PCT    default 70  (redundant with compactionThreshold:0.7 in settings.json)

CONTEXT_LIMIT=${CLAUDE_CONTEXT_LIMIT:-200000}
WARN_PCT=${CONTEXT_WARN_PCT:-60}
CRITICAL_PCT=${CONTEXT_CRITICAL_PCT:-70}

INPUT=$(cat 2>/dev/null || true)
SESSION_ID=$(echo "$INPUT" | grep -oE '"session_id"\s*:\s*"[^"]*"' 2>/dev/null | head -1 | grep -oE '"[^"]*"$' | tr -d '"' || true)

SESSION_FILE=""
if [ -n "$SESSION_ID" ]; then
  SESSION_FILE=$(find "$HOME/.claude/projects" -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1 || true)
fi

# Fallback: most recently touched .jsonl in same project dir
if [ -z "$SESSION_FILE" ] || [ ! -f "$SESSION_FILE" ]; then
  PROJECT_DIR=$(find "$HOME/.claude/projects" -maxdepth 1 -type d 2>/dev/null \
    | grep -i "$(basename "$(pwd)" | sed 's|[: ]|-|g')" | head -1 || true)
  if [ -n "$PROJECT_DIR" ]; then
    SESSION_FILE=$(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null | head -1 || true)
  fi
fi

# Last resort: most recently touched top-level .jsonl across all projects
if [ -z "$SESSION_FILE" ] || [ ! -f "$SESSION_FILE" ]; then
  SESSION_FILE=$(find "$HOME/.claude/projects" -maxdepth 2 -name "*.jsonl" 2>/dev/null \
    | xargs ls -t 2>/dev/null | head -1 || true)
fi

[ -z "$SESSION_FILE" ] && exit 0
[ ! -f "$SESSION_FILE" ] && exit 0

CACHE_TOKENS=$(tail -100 "$SESSION_FILE" 2>/dev/null \
  | grep -o '"cache_read_input_tokens":[0-9]*' \
  | tail -1 | grep -o '[0-9]*' || true)
INPUT_TOKENS=$(tail -100 "$SESSION_FILE" 2>/dev/null \
  | grep -o '"input_tokens":[0-9]*' \
  | tail -1 | grep -o '[0-9]*' || true)

CACHE_TOKENS=${CACHE_TOKENS:-0}
INPUT_TOKENS=${INPUT_TOKENS:-0}

ACTIVE_TOKENS=$(( CACHE_TOKENS + INPUT_TOKENS ))

case "$ACTIVE_TOKENS" in
  ''|*[!0-9]*) exit 0 ;;
esac

PCT=$(( ACTIVE_TOKENS * 100 / CONTEXT_LIMIT ))

if [ "$PCT" -lt "$WARN_PCT" ]; then
  exit 0
elif [ "$PCT" -lt "$CRITICAL_PCT" ]; then
  cat <<'EOF'
{"systemMessage": "⚠️  Context reaching limit — compaction will auto-trigger at 70%."}
EOF
  exit 0
else
  # >=70%: show banner AND spawn auto-enter to fire /compact (no rpi-trigger dependency)
  DELAY=8
  cat <<EOF
{"systemMessage": "🔴 Context at ~${PCT}% (${ACTIVE_TOKENS}/${CONTEXT_LIMIT} tokens). Running /compact automatically in ~${DELAY}s."}
EOF

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ENTER_SCRIPT="${SCRIPT_DIR}/../scripts/auto-enter-sender.ps1"
  WIN_PID_FILE="${HOME}/.agents/registry/claude-window-pid.txt"
  TARGET_PID=0
  if [ -f "$WIN_PID_FILE" ]; then
    TARGET_PID=$(cat "$WIN_PID_FILE" | tr -d '[:space:]' || true)
    [[ "$TARGET_PID" =~ ^[1-9][0-9]*$ ]] || TARGET_PID=0
  fi

  if [ -f "$ENTER_SCRIPT" ]; then
    WIN_SCRIPT=$(cygpath -w "$ENTER_SCRIPT" 2>/dev/null || echo "$ENTER_SCRIPT")
    nohup powershell.exe -WindowStyle Hidden -NonInteractive \
        -ExecutionPolicy Bypass \
        -File "$WIN_SCRIPT" -DelaySeconds "$DELAY" -TargetPid "$TARGET_PID" \
        >/dev/null 2>&1 &
    disown $! 2>/dev/null || true
  fi

  exit 0
fi
