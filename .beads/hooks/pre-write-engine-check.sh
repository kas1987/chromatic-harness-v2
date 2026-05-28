#!/usr/bin/env bash
# PreToolUse hook (matcher: Write|Edit): emit advisory systemMessage when the
# autonomous execution_engine has an active workstream claim that overlaps
# the file the human session is about to write.
#
# Never blocks. Per CLAUDE.md autonomous-mode policy, gate checks are
# informational only — the human chooses whether to defer.
#
# Input (stdin JSON):
#   {"tool_name": "Write", "tool_input": {"file_path": "..."}}
#
# Output (stdout JSON):
#   {} | {"systemMessage": "engine has active claim on overlapping path..."}
#
# Exit codes: 0 always (advisory). Failures are silent.

set -eu

# Fast-exit if jq or python missing — never block for tooling gaps.
command -v jq >/dev/null 2>&1 || { echo '{}'; exit 0; }
command -v python >/dev/null 2>&1 || { echo '{}'; exit 0; }

PAYLOAD="$(cat 2>/dev/null || true)"
[ -z "$PAYLOAD" ] && { echo '{}'; exit 0; }

TOOL_NAME="$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null)"
case "$TOOL_NAME" in
  Write|Edit|MultiEdit|NotebookEdit) ;;
  *) echo '{}'; exit 0 ;;
esac

FILE_PATH="$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[ -z "$FILE_PATH" ] && { echo '{}'; exit 0; }

# Find repo root so `python scripts/engine_status.py` resolves regardless
# of the session's cwd.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$REPO_ROOT" ] && { echo '{}'; exit 0; }

STATUS_SCRIPT="$REPO_ROOT/scripts/engine_status.py"
[ -f "$STATUS_SCRIPT" ] || { echo '{}'; exit 0; }

# Best-effort query — bail silently on any error.
STATUS_JSON="$(python "$STATUS_SCRIPT" --json 2>/dev/null || true)"
[ -z "$STATUS_JSON" ] && { echo '{}'; exit 0; }

ENGINE_ACTIVE="$(printf '%s' "$STATUS_JSON" | jq -r '.engine_active // false' 2>/dev/null)"
[ "$ENGINE_ACTIVE" != "true" ] && { echo '{}'; exit 0; }

# Engine is active. Check whether any active workstream's target_paths
# overlap the file we're about to write. Overlap = file_path startswith
# target_path (after normalizing both relative to repo root).
REL_PATH="${FILE_PATH#"$REPO_ROOT/"}"
REL_PATH="${REL_PATH#"$REPO_ROOT\\"}"

CONFLICT="$(printf '%s' "$STATUS_JSON" | jq -r --arg p "$REL_PATH" '
  .workstreams[]?
  | select(.target_paths != null)
  | select([.target_paths[] | select($p | startswith(.))] | length > 0)
  | "\(.epic_id) [\(.owner_agent)] expires \(.lease_expires_at)"
' 2>/dev/null | head -1)"

if [ -n "$CONFLICT" ]; then
  # Advisory only — emit systemMessage and let the write proceed.
  jq -nc --arg msg "engine collision: $CONFLICT has an active claim covering $REL_PATH (advisory — write proceeding; rerun \`python scripts/engine_status.py\` to inspect)" \
    '{systemMessage: $msg}'
  exit 0
fi

echo '{}'
exit 0
