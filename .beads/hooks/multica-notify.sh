#!/usr/bin/env bash
# Notifies Multica when a Claude Code Agent tool use completes.
# Set MULTICA_ISSUE_ID in the environment to update a specific issue.
# Requires multica CLI on PATH.

MULTICA_BIN_DEFAULT="$HOME/.multica/bin/multica"

if [ -z "$MULTICA_ISSUE_ID" ]; then
  exit 0
fi

# Prefer MULTICA_BIN env var, then home-dir binary, then PATH fallback.
if [ -n "${MULTICA_BIN:-}" ] && command -v "$MULTICA_BIN" &>/dev/null; then
  MULTICA_CMD="$MULTICA_BIN"
elif command -v "$MULTICA_BIN_DEFAULT" &>/dev/null; then
  MULTICA_CMD="$MULTICA_BIN_DEFAULT"
elif command -v multica &>/dev/null; then
  MULTICA_CMD="multica"
else
  exit 0
fi

# Read tool result from stdin (JSON from Claude Code hook protocol)
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Only act on Agent tool completions
if [ "$TOOL_NAME" != "Agent" ]; then
  exit 0
fi

# PostToolUse payload has no exit_code field — always transition to in_review.
# If future Claude Code versions expose stop_reason or exit_code, add failure detection here.
"$MULTICA_CMD" issue update "$MULTICA_ISSUE_ID" --status in_review 2>/dev/null || true
echo "[multica-notify] Agent completed — issue $MULTICA_ISSUE_ID → in_review" >&2
