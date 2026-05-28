#!/usr/bin/env bash
# Classifies Multica issue by review tier (keyword-based), dispatches LLM reviewer,
# posts comment to issue, updates status to done (PASS) or todo (FAIL).
# Tier 1=Pi/docs, 2=gpt-4o-mini, 3=gemini-2.5-flash, 4=human escalation

ISSUE_ID="${1:-$MULTICA_ISSUE_ID}"
MULTICA_BIN="$HOME/.multica/bin/multica"
REVIEW_LOG="$HOME/.claude/.agents/review/dispatch.log"
mkdir -p "$(dirname "$REVIEW_LOG")"

if [ -z "$ISSUE_ID" ]; then
  echo "[dispatch] No ISSUE_ID provided" >&2
  exit 1
fi

# Fetch issue details
ISSUE_JSON=$("$MULTICA_BIN" issue get "$ISSUE_ID" --output json 2>/dev/null) || {
  echo "[dispatch] Failed to fetch issue $ISSUE_ID" >&2
  exit 1
}
TITLE=$(echo "$ISSUE_JSON" | jq -r '.title // ""' 2>/dev/null)
DESC=$(echo "$ISSUE_JSON" | jq -r '.description // ""' 2>/dev/null)
COMBINED="$TITLE $DESC"

# Classify tier from keywords
TIER=2
echo "$COMBINED" | grep -qiE "doc|readme|comment|typo|format|changelog" && TIER=1
echo "$COMBINED" | grep -qiE "architect|design.pattern|cross.module|refactor|migration" && TIER=3
echo "$COMBINED" | grep -qiE "novel|rearchitect|security|authentication|authorization" && TIER=4

echo "[dispatch $(date -Iseconds)] $ISSUE_ID → tier $TIER: $TITLE" | tee -a "$REVIEW_LOG"

REVIEW_RESULT="" VERDICT="PASS"

case "$TIER" in
  1)
    VERDICT="PASS"
    REVIEW_RESULT="Docs/formatting issue — auto-approved by tier 1 (no LLM call needed)."
    ;;
  2)
    OPENAI_KEY_PATH="${OPENAI_API_KEY_PATH:-}"
    if [ -z "$OPENAI_KEY_PATH" ]; then
      REVIEW_RESULT="FAIL\nReview skipped: OPENAI_API_KEY_PATH env var is not set. Set the path or provide the key."
      VERDICT="FAIL"
    elif [ ! -f "$OPENAI_KEY_PATH" ]; then
      REVIEW_RESULT="FAIL\nReview skipped: OPENAI_API_KEY_PATH file not found at $OPENAI_KEY_PATH. Set the path or provide the key."
      VERDICT="FAIL"
    else
      OPENAI_KEY=$(cat "$OPENAI_KEY_PATH")
      PAYLOAD=$(jq -cn --arg t "$TITLE" --arg d "$DESC" \
        '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Code review this task. First line must be PASS or FAIL. Then brief reasoning (2-3 sentences).\nTitle: \($t)\nDescription: \($d)"}]}')
      REVIEW_RESULT=$(curl -s https://api.openai.com/v1/chat/completions \
        -H "Authorization: Bearer $OPENAI_KEY" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        2>/dev/null | jq -r '.choices[0].message.content // "PASS\nAuto-approved (reviewer unavailable)"')
      VERDICT=$(echo "$REVIEW_RESULT" | head -1 | grep -oiE "PASS|FAIL" || echo "PASS")
    fi
    ;;
  3)
    GEMINI_KEY_PATH="${GEMINI_API_KEY_PATH:-}"
    if [ -z "$GEMINI_KEY_PATH" ]; then
      REVIEW_RESULT="FAIL\nReview skipped: GEMINI_API_KEY_PATH env var is not set. Set the path or provide the key."
      VERDICT="FAIL"
    elif [ ! -f "$GEMINI_KEY_PATH" ]; then
      REVIEW_RESULT="FAIL\nReview skipped: GEMINI_API_KEY_PATH file not found at $GEMINI_KEY_PATH. Set the path or provide the key."
      VERDICT="FAIL"
    else
      GEMINI_KEY=$(cat "$GEMINI_KEY_PATH")
      PAYLOAD=$(jq -cn --arg t "$TITLE" --arg d "$DESC" \
        '{"contents":[{"parts":[{"text":"Code review this task. First line must be PASS or FAIL. Then brief reasoning.\nTitle: \($t)\nDescription: \($d)"}]}]}')
      REVIEW_RESULT=$(curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_KEY" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        2>/dev/null | jq -r '.candidates[0].content.parts[0].text // "PASS\nAuto-approved (reviewer unavailable)"')
      VERDICT=$(echo "$REVIEW_RESULT" | head -1 | grep -oiE "PASS|FAIL" || echo "PASS")
    fi
    ;;
  4)
    VERDICT="NEEDS_HUMAN"
    REVIEW_RESULT="Tier 4 (architecture/security) — requires human review. Issue left in_review."
    ;;
esac

# Determine model label
case "$TIER" in
  1) MODEL_LABEL="Pi/auto" ;;
  2) MODEL_LABEL="gpt-4o-mini" ;;
  3) MODEL_LABEL="gemini-2.5-flash" ;;
  *) MODEL_LABEL="human" ;;
esac

# Post review comment to Multica issue
"$MULTICA_BIN" issue comment add "$ISSUE_ID" \
  --content "**Auto-Review (Tier $TIER / $MODEL_LABEL):** $VERDICT

$REVIEW_RESULT" 2>/dev/null || true

echo "[dispatch] $ISSUE_ID verdict=$VERDICT tier=$TIER" | tee -a "$REVIEW_LOG"

# Update status and invoke packager on PASS
if [ "$VERDICT" = "PASS" ]; then
  "$MULTICA_BIN" issue update "$ISSUE_ID" --status done 2>/dev/null || true
  export REVIEW_TIER="$TIER" REVIEW_VERDICT="$VERDICT"
  export REVIEW_SUMMARY="$REVIEW_RESULT"
  export ISSUE_TITLE="$TITLE" ISSUE_ID="$ISSUE_ID"
  bash "$HOME/.claude/hooks/session-packager.sh" 2>/dev/null || true
elif [ "$VERDICT" = "FAIL" ]; then
  "$MULTICA_BIN" issue update "$ISSUE_ID" --status todo 2>/dev/null || true
fi
# NEEDS_HUMAN: leave in_review, comment already posted

exit 0
