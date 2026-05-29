#!/usr/bin/env bash
# PostToolUse Bash hook — detects bd create output, classifies tier, writes to repo intake queue.
# Fires after every Bash call; exits fast when not a bead creation event.

HOOK_DATA=$(cat)

# Only act on Bash tool calls
TOOL_NAME=$(echo "$HOOK_DATA" | jq -r '.tool_name // empty' 2>/dev/null)
[ "$TOOL_NAME" = "Bash" ] || exit 0

# Check if the bash command included bd create
CMD=$(echo "$HOOK_DATA" | jq -r '.tool_input.command // empty' 2>/dev/null)
echo "$CMD" | grep -q 'bd create' || exit 0

# Repo-root queue (chromatic-harness-v2 contract)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -n "$REPO_ROOT" ] || exit 0
QUEUE="${REPO_ROOT}/07_LOGS_AND_AUDIT/intake_queue.jsonl"
mkdir -p "$(dirname "${QUEUE}")" 2>/dev/null || true

# Extract bead ID from tool output
RESPONSE=$(echo "$HOOK_DATA" | jq -r '.tool_response // empty' 2>/dev/null)
BEAD_ID=$(echo "$RESPONSE" | grep -oE 'chromatic-harness-v2-[a-z0-9]+' | head -1)
[ -n "$BEAD_ID" ] || BEAD_ID=$(echo "$RESPONSE" | grep -oE '\b[a-z]{2}-[a-zA-Z0-9]{3,5}\b' | head -1)
[ -n "$BEAD_ID" ] || exit 0

# Don't re-queue while already queued
grep -q "\"id\":\"${BEAD_ID}\"" "${QUEUE}" 2>/dev/null && grep -q '"status":"queued"' "${QUEUE}" 2>/dev/null && exit 0

# Fetch bead metadata (5s timeout)
BEAD_JSON=$(timeout 5 bd show "${BEAD_ID}" --json 2>/dev/null) || {
  TITLE=$(echo "$RESPONSE" | sed -n 's/.*Created issue: //p' | head -1)
  BEAD_JSON="{\"id\":\"${BEAD_ID}\",\"title\":\"${TITLE}\",\"priority\":\"P2\",\"type\":\"task\",\"description\":\"\"}"
}

TITLE=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .title // empty' 2>/dev/null)
PRIORITY=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .priority // "P2"' 2>/dev/null)
BEAD_TYPE=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .type // "task"' 2>/dev/null)
DESC=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .description // empty' 2>/dev/null)
COMBINED="${TITLE} ${DESC}"

# Classify OL tier
TIER=3
echo "$COMBINED" | grep -qiE 'frontmatter|scaffold|boilerplate|seed|readme|changelog|template|fixture|add.*block|add.*field|add.*line' && TIER=0
echo "$COMBINED" | grep -qiE 'doc|comment|typo|format|rename|single.file|permissions|allowed|forbidden' && TIER=1
echo "$COMBINED" | grep -qiE 'smoke|spec.compliance|pr.review|single.*test|verify|check|guard|flag' && TIER=2
echo "$COMBINED" | grep -qiE 'multi.file|cross.module|refactor|integration|debug|root.cause|design|architecture|orchestrat' && TIER=3
echo "$COMBINED" | grep -qiE 'novel|rearchitect|security|authentication|authorization|brainstorm|pre.mortem|tradeoff' && TIER=4
[ "$PRIORITY" = "P1" ] && [ "$TIER" -lt 2 ] && TIER=2

ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
jq -cn \
  --arg id "${BEAD_ID}" \
  --arg bead_id "${BEAD_ID}" \
  --arg title "${TITLE}" \
  --arg priority "${PRIORITY}" \
  --arg bead_type "${BEAD_TYPE}" \
  --argjson tier "${TIER}" \
  --arg queued_at "${ts}" \
  '{
    id: $id,
    source: "bead_hook",
    kind: "bead_dispatch",
    status: "queued",
    title: $title,
    bead_id: $bead_id,
    priority: $priority,
    type: $bead_type,
    tier: $tier,
    queued_at: $queued_at
  }' >> "${QUEUE}" 2>/dev/null || true

echo "[bead-intake] Queued ${BEAD_ID} (tier ${TIER}) → ${QUEUE}" >&2
exit 0
