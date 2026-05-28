#!/usr/bin/env bash
# next-steps-reinjector.sh — UserPromptSubmit hook
#
# When the user submits a message that references a prior "Next Steps" item
# (by number, or with intent words like "go"/"do it"/"proceed"/"step N"),
# re-injects the last governance confidence annotation as a systemMessage
# so Claude has the empirical confidence data in context.
#
# Reads: ~/.agents/registry/last-confidence-annotation.json
# Best-effort: always exits 0.
set -euo pipefail

REGISTRY_DIR="${USERPROFILE:-$HOME}/.agents/registry"
LAST_ANN="${REGISTRY_DIR}/last-confidence-annotation.json"

# Bail if no annotation on disk
[[ -f "$LAST_ANN" ]] || exit 0

# Read the user prompt from stdin (UserPromptSubmit passes JSON)
INPUT=$(cat 2>/dev/null || true)
[[ -z "$INPUT" ]] && exit 0

PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || true)
[[ -z "$PROMPT" ]] && exit 0

# ── Staleness check: annotation > 30 minutes old → don't re-inject ───────────
ANN_TS=$(jq -r '.ts // ""' "$LAST_ANN" 2>/dev/null || true)
if [[ -n "$ANN_TS" ]]; then
  ANN_EPOCH=$(date -u -d "$ANN_TS" +%s 2>/dev/null || echo 0)
  NOW_EPOCH=$(date -u +%s)
  AGE=$(( NOW_EPOCH - ANN_EPOCH ))
  (( AGE > 1800 )) && exit 0   # >30 min stale
fi

# ── Detect step-reference intent in the prompt ────────────────────────────────
PROMPT_LOWER=$(printf '%s' "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Patterns that signal the user is acting on the last Next Steps list:
#   "go", "do it", "proceed", "start", "execute", "run it",
#   "step 1" / "step one" / "#1" / "do step 2" / "item 3"
STEP_REFERENCE=0

# Short command words (<=5 chars, standalone)
if echo "$PROMPT_LOWER" | grep -qxE '[[:space:]]*(go|do|run|yes|ok|yep|sure|start|ship|next|exec|fire)[[:space:]!.]*'; then
  STEP_REFERENCE=1
fi

# Explicit step references
if echo "$PROMPT_LOWER" | grep -qE '(step|item|#)[[:space:]]*[0-9]|do it|proceed|execute|run it|start it|carry on|continue'; then
  STEP_REFERENCE=1
fi

# "do step N", "step N please", "run step N"
if echo "$PROMPT_LOWER" | grep -qE '\b(step|item|number)[[:space:]]*[1-9]\b'; then
  STEP_REFERENCE=1
fi

[[ "$STEP_REFERENCE" == 0 ]] && exit 0

# ── Re-inject the last annotation ────────────────────────────────────────────
ANNOTATION=$(jq -r '.message // ""' "$LAST_ANN" 2>/dev/null || true)
[[ -z "$ANNOTATION" ]] && exit 0

STEP_COUNT=$(jq -r '.step_count // 0' "$LAST_ANN" 2>/dev/null || echo 0)
REINJECT_MSG="[Re-injecting governance confidence from last Next Steps (${STEP_COUNT} steps)]
${ANNOTATION}"

jq -cn --arg m "$REINJECT_MSG" '{"systemMessage": $m}'
exit 0
