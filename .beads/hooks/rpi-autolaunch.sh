#!/usr/bin/env bash
# rpi-autolaunch.sh — Stop hook (second group; runs after next-steps-confidence)
#
# When HIGH next-steps were just committed to beads:
#   - outputs systemMessage immediately
#   - spawns detached PowerShell that waits 30-60s and sends Enter automatically
#   - context remaining > 30%: /rpi directive
#   - context remaining ≤ 30%: /compact directive
#
# Trigger: ~/.agents/registry/rpi-trigger.flag (written by next-steps-confidence.sh)
# Best-effort: always exits 0.
set -euo pipefail

TRIGGER="${HOME}/.agents/registry/rpi-trigger.flag"
[ -f "$TRIGGER" ] || exit 0
rm -f "$TRIGGER"

command -v python3 >/dev/null 2>&1 || exit 0

# Read Stop event for session_id → locate session JSONL for context check
INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0

SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // .sessionId // empty' 2>/dev/null || true)
[ -z "$SESSION_ID" ] && exit 0

SESSION_FILE=$(find "${HOME}/.claude/projects" -maxdepth 2 -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1 || true)
[ -f "$SESSION_FILE" ] || exit 0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_SCRIPT="${SCRIPT_DIR}/../scripts/context-from-session.py"
[ -f "$CONTEXT_SCRIPT" ] || exit 0

# Compute context usage — model-aware, delegated to script
CONTEXT_INFO=$(python3 "$CONTEXT_SCRIPT" "$SESSION_FILE" 2>/dev/null || echo "0,100,unknown,200000")

PCT_USED=$(echo "$CONTEXT_INFO"      | cut -d',' -f1)
PCT_REMAINING=$(echo "$CONTEXT_INFO" | cut -d',' -f2)
MODEL=$(echo "$CONTEXT_INFO"         | cut -d',' -f3)

# Float comparison: remaining >= 30 → launch /rpi; else → compact
REMAINING_OK=$(awk "BEGIN{print ($PCT_REMAINING + 0 >= 30) ? \"yes\" : \"no\"}")

# Delay for the auto-enter sender (30-60s grace for user to read the response)
DELAY=$(( RANDOM % 31 + 30 ))

ENTER_SCRIPT="${SCRIPT_DIR}/../scripts/auto-enter-sender.ps1"

if [ "$REMAINING_OK" = "yes" ]; then
    MSG="[AUTOLAUNCH] HIGH next-steps committed to beads (${PCT_USED}% used, ${PCT_REMAINING}% remaining on ${MODEL}). /rpi will fire automatically in ~${DELAY}s."
    jq -cn --arg m "$MSG" '{"systemMessage": $m}'
else
    MSG="[AUTOCOMPACT] Context at ${PCT_USED}% used (${PCT_REMAINING}% remaining on ${MODEL}) — below 30% threshold. /compact will fire automatically in ~${DELAY}s."
    jq -cn --arg m "$MSG" '{"systemMessage": $m}'
fi

# Spawn detached PowerShell to send Enter after the grace period
if [ -f "$ENTER_SCRIPT" ]; then
    WIN_SCRIPT=$(cygpath -w "$ENTER_SCRIPT" 2>/dev/null || echo "$ENTER_SCRIPT")
    WIN_PID_FILE="${HOME}/.agents/registry/claude-window-pid.txt"
    TARGET_PID=0
    if [ -f "$WIN_PID_FILE" ]; then
        TARGET_PID=$(cat "$WIN_PID_FILE" | tr -d '[:space:]' || true)
        [[ "$TARGET_PID" =~ ^[1-9][0-9]*$ ]] || TARGET_PID=0
    fi
    nohup powershell.exe -WindowStyle Hidden -NonInteractive \
        -ExecutionPolicy Bypass \
        -File "$WIN_SCRIPT" -DelaySeconds "$DELAY" -TargetPid "$TARGET_PID" \
        >/dev/null 2>&1 &
    disown $! 2>/dev/null || true
fi

exit 0
