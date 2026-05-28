#!/usr/bin/env bash
# next-steps-confidence.sh — Stop hook
# Detects "Next Steps" in the last assistant turn and injects a
# governance-layer confidence annotation as a systemMessage.
# Best-effort: always exits 0.
set -euo pipefail

# Fast bail if Python not available
command -v python3 >/dev/null 2>&1 || exit 0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIDENCE_SCRIPT="${SCRIPT_DIR}/../scripts/next-steps-confidence.py"
[ -f "$CONFIDENCE_SCRIPT" ] || exit 0

# Read Stop event JSON from stdin
INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0

# Extract session_id
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // .sessionId // empty' 2>/dev/null || true)
[ -z "$SESSION_ID" ] && exit 0

# Locate session JSONL — check hook's cwd project dir first, then scan all projects
PROJECTS_DIR="${HOME}/.claude/projects"
SESSION_FILE=""

# Direct match by session_id (fastest)
for candidate in "${PROJECTS_DIR}"/**/"${SESSION_ID}.jsonl" "${PROJECTS_DIR}/${SESSION_ID}.jsonl"; do
  [[ -f "$candidate" ]] && SESSION_FILE="$candidate" && break
done

# Fallback: scan for session_id in filename across project dirs
if [ -z "$SESSION_FILE" ]; then
  SESSION_FILE=$(find "$PROJECTS_DIR" -maxdepth 2 -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1 || true)
fi

[ -z "$SESSION_FILE" ] && exit 0
[ ! -f "$SESSION_FILE" ] && exit 0

# Run confidence analysis — outputs {"systemMessage": "..."} or nothing
RESULT=$(PYTHONIOENCODING=utf-8 python3 "$CONFIDENCE_SCRIPT" "$SESSION_FILE" 2>/dev/null || true)

[ -n "$RESULT" ] && printf '%s\n' "$RESULT"

# Auto-add HIGH-confidence next steps to beads; write trigger for rpi-autolaunch
ANN_FILE="${HOME}/.agents/registry/last-confidence-annotation.json"
TRIGGER="${HOME}/.agents/registry/rpi-trigger.flag"
BEADS_SCRIPT="${SCRIPT_DIR}/../scripts/beads-from-steps.py"
if command -v bd >/dev/null 2>&1 && [ -f "$ANN_FILE" ] && [ -f "$BEADS_SCRIPT" ]; then
  CREATED=0
  # Python outputs HIGH steps NUL-delimited; bash calls bd create (bd needs shell PATH)
  while IFS= read -r -d '' step; do
    [ -z "$step" ] && continue
    title="${step:0:120}"
    if bd create "$title" --type task --description "$step" >/dev/null 2>&1; then
      CREATED=$(( CREATED + 1 ))
    fi
  done < <(python3 "$BEADS_SCRIPT" "$ANN_FILE" 2>/dev/null || true)
  [ "${CREATED}" -gt 0 ] && touch "$TRIGGER"
fi

exit 0
