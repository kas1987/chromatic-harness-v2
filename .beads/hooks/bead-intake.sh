#!/usr/bin/env bash
# PostToolUse Bash hook — detects bd create output, classifies tier, writes to intake queue.
# Fires after every Bash call; exits fast when not a bead creation event.

INTAKE_DIR="${HOME}/.claude/.agents/intake"
QUEUE="${INTAKE_DIR}/queue.jsonl"
mkdir -p "${INTAKE_DIR}" 2>/dev/null || true

HOOK_DATA=$(cat)

# Only act on Bash tool calls
TOOL_NAME=$(echo "$HOOK_DATA" | jq -r '.tool_name // empty' 2>/dev/null)
[ "$TOOL_NAME" = "Bash" ] || exit 0

# Check if the bash command included bd create
CMD=$(echo "$HOOK_DATA" | jq -r '.tool_input.command // empty' 2>/dev/null)
echo "$CMD" | grep -q 'bd create' || exit 0

# Extract bead ID from tool output (matches "✓ Created issue: <id>" or "Created bead: <id>")
RESPONSE=$(echo "$HOOK_DATA" | jq -r '.tool_response // empty' 2>/dev/null)
BEAD_ID=$(echo "$RESPONSE" | grep -oE '\b[a-z]{2}-[a-zA-Z0-9]{3,5}\b' | head -1)
[ -n "$BEAD_ID" ] || exit 0

# Don't re-queue already-queued beads
grep -q "\"id\":\"${BEAD_ID}\"" "${QUEUE}" 2>/dev/null && exit 0

# Fetch bead metadata (5s timeout — bd show can hang from WSL against Windows-native CLI)
BEAD_JSON=$(timeout 5 bd show "${BEAD_ID}" --json 2>/dev/null) || {
  # Fallback: parse from response text
  TITLE=$(echo "$RESPONSE" | grep -oP '(?<=Created issue: )[^\n]+' | head -1)
  BEAD_JSON="{\"id\":\"${BEAD_ID}\",\"title\":\"${TITLE}\",\"priority\":\"P2\",\"type\":\"task\",\"description\":\"\"}"
}

TITLE=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .title // empty' 2>/dev/null)
PRIORITY=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .priority // "P2"' 2>/dev/null)
BEAD_TYPE=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .type // "task"' 2>/dev/null)
DESC=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .description // empty' 2>/dev/null)
COMBINED="${TITLE} ${DESC}"

# Classify OL tier (matches CLAUDE.md multi-router-matrix routing rules)
TIER=3
echo "$COMBINED" | grep -qiE 'frontmatter|scaffold|boilerplate|seed|readme|changelog|template|fixture|add.*block|add.*field|add.*line' && TIER=0
echo "$COMBINED" | grep -qiE 'doc|comment|typo|format|rename|single.file|permissions|allowed|forbidden' && TIER=1
echo "$COMBINED" | grep -qiE 'smoke|spec.compliance|pr.review|single.*test|verify|check|guard|flag' && TIER=2
echo "$COMBINED" | grep -qiE 'multi.file|cross.module|refactor|integration|debug|root.cause|design|architecture|orchestrat' && TIER=3
echo "$COMBINED" | grep -qiE 'novel|rearchitect|security|authentication|authorization|brainstorm|pre.mortem|tradeoff' && TIER=4

# Upgrade low tiers based on priority
[ "$PRIORITY" = "P1" ] && [ "$TIER" -lt 2 ] && TIER=2

# Write to intake queue
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
jq -cn \
  --arg id "${BEAD_ID}" \
  --arg title "${TITLE}" \
  --arg priority "${PRIORITY}" \
  --arg bead_type "${BEAD_TYPE}" \
  --argjson tier "${TIER}" \
  --arg status "queued" \
  --arg queued_at "${ts}" \
  '{id:$id,title:$title,priority:$priority,type:$bead_type,tier:$tier,status:$status,queued_at:$queued_at}' \
  >> "${QUEUE}" 2>/dev/null || true

echo "[bead-intake] Queued ${BEAD_ID} (tier ${TIER}): ${TITLE}" >&2

exit 0
