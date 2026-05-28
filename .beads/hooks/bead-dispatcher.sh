#!/usr/bin/env bash
# bead-dispatcher.sh — SessionStart hook: reads intake queue, claims unclaimed beads, outputs dispatch plan.
# Safety rails: circuit-breaker on bd calls, max-items cap, timeout guards, stale-queue rotation.
# T0-T2: dispatched to OL layer via multi-provider-dispatch.sh (if available)
# T3-T4: surfaced to orchestrator for Claude-level execution in this session.
#
# Queue format: one compact JSON object per line (JSONL).
# Status lifecycle: queued → dispatched → done | skipped

set -u

# ── Circuit breaker ──────────────────────────────────────────────────────────
CB_DIR="${HOME}/.claude/.agents/circuit-breaker"
mkdir -p "${CB_DIR}" 2>/dev/null || true
BD_CB_FILE="${CB_DIR}/bead-dispatcher.failures"

# If circuit breaker is open (3+ consecutive failures), exit fast
if [ -f "${CB_DIR}/bead-dispatcher.disabled" ]; then
  exit 0
fi

BD_FAIL_COUNT=0
if [ -f "${BD_CB_FILE}" ]; then
  BD_FAIL_COUNT=$(cat "${BD_CB_FILE}" 2>/dev/null | tr -d '[:space:]')
  BD_FAIL_COUNT=${BD_FAIL_COUNT:-0}
fi
if [ "${BD_FAIL_COUNT}" -ge 3 ]; then
  touch "${CB_DIR}/bead-dispatcher.disabled" 2>/dev/null || true
  exit 0
fi

# ── Config / safety caps ──────────────────────────────────────────────────────
MAX_ITEMS="${BEAD_DISPATCHER_MAX:-20}"     # Safety: never process more than N items
BD_TIMEOUT="${BEAD_BD_TIMEOUT:-3}"          # Per bd call timeout
READY_TIMEOUT="${BEAD_READY_TIMEOUT:-3}"   # bd ready timeout
OL_TIMEOUT="${BEAD_OL_TIMEOUT:-10}"        # OL dispatch timeout per item

INTAKE_DIR="${HOME}/.claude/.agents/intake"
QUEUE="${INTAKE_DIR}/queue.jsonl"
DISPATCH_LOG="${INTAKE_DIR}/dispatch.jsonl"
DISPATCH_SH="${HOME}/.claude/hooks/multi-provider-dispatch.sh"

mkdir -p "${INTAKE_DIR}" 2>/dev/null || true
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)

# ── helpers ──────────────────────────────────────────────────────────────────

classify_tier() {
  local combined="$1" priority="$2" tier=3
  echo "$combined" | grep -qiE 'frontmatter|scaffold|boilerplate|seed|readme|changelog|template|fixture|add.*block|add.*field|add.*line' && tier=0
  echo "$combined" | grep -qiE 'doc|comment|typo|format|rename|single.file|permissions|allowed|forbidden' && tier=1
  echo "$combined" | grep -qiE 'smoke|spec.compliance|pr.review|single.*test|verify|check|guard|flag' && tier=2
  echo "$combined" | grep -qiE 'multi.file|cross.module|refactor|integration|debug|root.cause|design|architecture|orchestrat' && tier=3
  echo "$combined" | grep -qiE 'novel|rearchitect|security|authentication|authorization|brainstorm|pre.mortem|tradeoff' && tier=4
  [ "$priority" = "P1" ] && [ "$tier" -lt 2 ] && tier=2
  echo "$tier"
}

update_queue_status() {
  local id="$1" new_status="$2"
  local tmpf="${QUEUE}.tmp.$$"
  jq -c --arg id "$id" --arg s "$new_status" --arg ts "$ts" \
    'if .id == $id then .status = $s | .dispatched_at = $ts else . end' \
    "${QUEUE}" > "${tmpf}" 2>/dev/null \
    && mv "${tmpf}" "${QUEUE}" 2>/dev/null \
    || rm -f "${tmpf}" 2>/dev/null
}

in_queue() {
  local id="$1"
  [ -f "${QUEUE}" ] && grep -q "\"id\":\"${id}\"" "${QUEUE}" 2>/dev/null
}

record_fail() {
  BD_FAIL_COUNT=$((BD_FAIL_COUNT + 1))
  printf '%d' "${BD_FAIL_COUNT}" > "${BD_CB_FILE}" 2>/dev/null || true
  if [ "${BD_FAIL_COUNT}" -ge 3 ]; then
    touch "${CB_DIR}/bead-dispatcher.disabled" 2>/dev/null || true
  fi
}

record_success() {
  printf '0' > "${BD_CB_FILE}" 2>/dev/null || true
}

# ── Step 0: Stale queue rotation (safety rail) ────────────────────────────────
# If queue has >500 entries, archive the old ones to prevent unbounded growth
if [ -f "${QUEUE}" ]; then
  QUEUE_LINES=$(wc -l < "${QUEUE}" 2>/dev/null || echo 0)
  if [ "${QUEUE_LINES}" -gt 500 ]; then
    ARCHIVE="${INTAKE_DIR}/queue-archive-$(date +%Y%m%d).jsonl"
    # Keep only "queued" or recently active entries; archive the rest
    jq -c 'select(.status == "queued" or (.dispatched_at // "" | . > (now - 86400 | strftime("%Y-%m-%dT%H:%M:%SZ"))))' \
      "${QUEUE}" > "${QUEUE}.new" 2>/dev/null \
      && cp "${QUEUE}" "${ARCHIVE}" 2>/dev/null \
      && mv "${QUEUE}.new" "${QUEUE}" 2>/dev/null \
      || rm -f "${QUEUE}.new" 2>/dev/null
  fi
fi

# ── Step 1: Sync — mark done any dispatched beads that are now closed in bd ──
# Safety: limit sync to first MAX_ITEMS entries to prevent runaway bd show calls

sync_count=0
SYNC_MAX=3  # Safety: never sync more than 3 dispatched items per session
SYNC_BD_TIMEOUT=1  # 1s timeout for sync checks (non-critical housekeeping, fail fast)
if [ -f "${QUEUE}" ] && command -v bd &>/dev/null; then
  # Only look at dispatched items, limit to SYNC_MAX to prevent runaway
  while IFS= read -r entry; do
    [ "${sync_count}" -ge "${SYNC_MAX}" ] && break
    ID=$(echo "$entry" | jq -r '.id' 2>/dev/null)
    STATUS=$(echo "$entry" | jq -r '.status' 2>/dev/null)
    [ "$STATUS" = "dispatched" ] || continue
    BD_STATUS=$(timeout "${SYNC_BD_TIMEOUT}" bd show "$ID" --json 2>/dev/null | jq -r '(if type=="array" then .[0] else . end) | .status // empty' 2>/dev/null)
    if [ "$BD_STATUS" = "closed" ] || [ "$BD_STATUS" = "done" ]; then
      update_queue_status "$ID" "done"
    fi
    sync_count=$((sync_count + 1))
  done < <(grep '"dispatched"' "${QUEUE}" 2>/dev/null | head -"${SYNC_MAX}")
fi

# ── Step 2: Ingest new open beads not yet in queue ────────────────────────────
# Safety: cap ingestion, timeout each bd call

ingest_count=0
if command -v bd &>/dev/null && command -v jq &>/dev/null; then
  while IFS= read -r bead_id; do
    [ -z "$bead_id" ] && continue
    [ "${ingest_count}" -ge "${MAX_ITEMS}" ] && break
    in_queue "$bead_id" && continue
    BEAD_JSON=$(timeout "${BD_TIMEOUT}" bd show "${bead_id}" --json 2>/dev/null) || continue
    [ -z "$BEAD_JSON" ] && continue
    TITLE=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .title // empty' 2>/dev/null)
    PRIORITY=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .priority // "P2"' 2>/dev/null)
    BEAD_TYPE=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .type // "task"' 2>/dev/null)
    DESC=$(echo "$BEAD_JSON" | jq -r '(if type=="array" then .[0] else . end) | .description // empty' 2>/dev/null)
    TIER=$(classify_tier "${TITLE} ${DESC}" "$PRIORITY")
    jq -cn \
      --arg id "${bead_id}" \
      --arg title "${TITLE}" \
      --arg priority "${PRIORITY}" \
      --arg bead_type "${BEAD_TYPE}" \
      --argjson tier "${TIER}" \
      --arg status "queued" \
      --arg queued_at "${ts}" \
      '{id:$id,title:$title,priority:$priority,type:$bead_type,tier:$tier,status:$status,queued_at:$queued_at}' \
      >> "${QUEUE}" 2>/dev/null || true
    ingest_count=$((ingest_count + 1))
  done < <(timeout "${READY_TIMEOUT}" bd ready 2>/dev/null | grep -oE '\b[a-z]{2}-[a-zA-Z0-9]{3,5}\b' | head -"${MAX_ITEMS}")
fi

[ -f "${QUEUE}" ] || { record_fail; exit 0; }

# ── Step 3: Pick queued items (capped) ────────────────────────────────────────

PENDING=$(jq -s '
  [ .[] | select(.status == "queued") ] |
  sort_by([
    (if .priority == "P1" then 0 elif .priority == "P2" then 1 else 2 end),
    .tier
  ]) | .[0:' + "${MAX_ITEMS}" + ']
' "${QUEUE}" 2>/dev/null)

COUNT=$(echo "$PENDING" | jq 'length' 2>/dev/null)
COUNT=${COUNT:-0}
[ "${COUNT}" -eq 0 ] && { record_success; exit 0; }

echo ""
echo "=== BEAD DISPATCHER: ${COUNT} item(s) queued for dispatch ==="

OL_ITEMS=()
SESSION_ITEMS=()

while IFS= read -r item; do
  [ -z "$item" ] && continue
  ID=$(echo "$item" | jq -r '.id' 2>/dev/null)
  TITLE=$(echo "$item" | jq -r '.title' 2>/dev/null)
  TIER=$(echo "$item" | jq -r '.tier' 2>/dev/null)
  PRIORITY=$(echo "$item" | jq -r '.priority' 2>/dev/null)

  if [ "$TIER" -le 2 ] 2>/dev/null; then
    OL_ITEMS+=("${ID}|${TIER}|${PRIORITY}|${TITLE}")
    echo "  [OL T${TIER}] ${ID} (${PRIORITY}): ${TITLE}"
  else
    SESSION_ITEMS+=("${ID}|${TIER}|${PRIORITY}|${TITLE}")
    echo "  [SESSION T${TIER}] ${ID} (${PRIORITY}): ${TITLE}"
  fi

  update_queue_status "$ID" "dispatched"
  timeout "${BD_TIMEOUT}" bd update "${ID}" --status in_progress 2>/dev/null || true
  # Guard: only append to dispatch log if ID not already present
  if ! grep -q "\"id\":\"${ID}\"" "${DISPATCH_LOG}" 2>/dev/null; then
    jq -cn --arg id "$ID" --arg title "$TITLE" --argjson tier "${TIER}" \
      --arg priority "$PRIORITY" --arg ts "$ts" \
      '{id:$id,title:$title,tier:$tier,priority:$priority,dispatched_at:$ts}' \
      >> "${DISPATCH_LOG}" 2>/dev/null || true
  fi

done < <(echo "$PENDING" | jq -c '.[]' 2>/dev/null)

# ── Step 4: OL dispatch (T0-T2) — with per-item timeout and fallback ────────

if [ "${#OL_ITEMS[@]}" -gt 0 ] && [ -x "${DISPATCH_SH}" ]; then
  echo ""
  echo "  Dispatching ${#OL_ITEMS[@]} item(s) to OL layer..."
  for entry in "${OL_ITEMS[@]}"; do
    IFS='|' read -r ID TIER PRIORITY TITLE <<< "$entry"
    PROMPT_FILE="${INTAKE_DIR}/prompt-${ID}.txt"
    DESC=$(timeout "${BD_TIMEOUT}" bd show "${ID}" 2>/dev/null | grep -A20 "DESCRIPTION" | tail -n +2 | head -15)
    KEYWORDS=$(echo "$TITLE" | grep -oP '[a-zA-Z_][a-zA-Z0-9_\-]{3,}' | grep -v '^mc-' | head -5 | tr '\n' '|' | sed 's/|$//')
    FILE_CONTEXT=""
    if [ -n "$KEYWORDS" ]; then
      FILE_CONTEXT=$(timeout 3 grep -rl --include="*.sh" --include="*.md" -E "$KEYWORDS" \
        "${HOME}/.claude/hooks" "${HOME}/.claude/skills" 2>/dev/null \
        | head -5 \
        | while IFS= read -r f; do
            echo "--- $f ---"
            grep -n -E "$KEYWORDS" "$f" 2>/dev/null | head -8
          done)
    fi
    printf 'Task: %s\n\nDescription:\n%s\n\n[Relevant file excerpts for context — do not repeat these in your answer]\n%s\n\nYour answer: Output ONLY the exact file change needed.\nFormat: **File:** `<absolute-path>`\n```\n<new or modified text>\n```\n' \
      "${TITLE}" "${DESC}" "${FILE_CONTEXT}" > "${PROMPT_FILE}"
    RESULT=$(timeout "${OL_TIMEOUT}" "${DISPATCH_SH}" "${TIER}" "${PROMPT_FILE}" 2>/dev/null)
    DISPATCH_OK=$?
    CONTENT=$(echo "$RESULT" | jq -r '.choices[0].message.content // .content // .response // empty' 2>/dev/null)
    if [ $DISPATCH_OK -eq 0 ] && [ -n "$CONTENT" ]; then
      echo "  ✓ OL T${TIER} dispatched: ${ID}"
      jq -cn --arg id "$ID" --arg content "$CONTENT" --arg ts "$ts" \
        '{id:$id,content:$content,completed_at:$ts}' \
        >> "${INTAKE_DIR}/ol-results.jsonl" 2>/dev/null || true
    else
      echo "  ✗ OL dispatch failed for ${ID} (tier ${TIER}) — session will handle"
      SESSION_ITEMS+=("${ID}|${TIER}|${PRIORITY}|${TITLE}")
    fi
  done
fi

# ── Step 5: Surface session items ─────────────────────────────────────────────

if [ "${#SESSION_ITEMS[@]}" -gt 0 ]; then
  echo ""
  echo "  SESSION WORK (T3-T4 — Claude orchestrator handles these):"
  for entry in "${SESSION_ITEMS[@]}"; do
    IFS='|' read -r ID TIER PRIORITY TITLE <<< "$entry"
    echo "    /implement ${ID}  ← ${PRIORITY} T${TIER}: ${TITLE}"
  done
  echo ""
  echo "  Run /implement <id> or /rpi --from=implementation <id> to execute."
fi

record_success
echo "=== BEAD DISPATCHER DONE ==="
echo ""
exit 0