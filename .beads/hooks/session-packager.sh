#!/usr/bin/env bash
# Bundles git diff + test results + review summary into a markdown deliverable.
# Invoked by review-dispatch.sh on PASS verdict.
# Env: ISSUE_ID, ISSUE_TITLE, REVIEW_TIER, REVIEW_VERDICT, REVIEW_SUMMARY

OUTPUT_DIR="$HOME/.claude/.agents/review/deliverables"
mkdir -p "$OUTPUT_DIR"

ISSUE_ID="${ISSUE_ID:-unknown}"
ISSUE_TITLE="${ISSUE_TITLE:-Untitled}"
REVIEW_TIER="${REVIEW_TIER:-2}"
REVIEW_VERDICT="${REVIEW_VERDICT:-PASS}"
REVIEW_SUMMARY="${REVIEW_SUMMARY:-No summary available}"

SLUG=$(date +%Y-%m-%d)-${ISSUE_ID}
OUTFILE="$OUTPUT_DIR/$SLUG.md"

{
  echo "# Deliverable: $ISSUE_TITLE"
  echo ""
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| Issue | $ISSUE_ID |"
  echo "| Review Tier | $REVIEW_TIER |"
  echo "| Verdict | $REVIEW_VERDICT |"
  echo "| Packaged | $(date -Iseconds) |"
  echo ""
  echo "## Review Summary"
  echo ""
  echo "$REVIEW_SUMMARY"
  echo ""
  echo "## Git Diff"
  echo ""
  echo '```diff'
  git diff HEAD~1 2>/dev/null || git diff --cached 2>/dev/null || echo "(no diff available)"
  echo '```'
  echo ""
  echo "## Test Results"
  echo ""
  if [ -f "$HOME/.claude/.agents/test/last-pass.json" ]; then
    cat "$HOME/.claude/.agents/test/last-pass.json"
  else
    echo "_No test results recorded._"
  fi
} > "$OUTFILE"

echo "[packager] Deliverable written: $OUTFILE" >&2

# Signal auto-push
export DELIVERABLE_FILE="$OUTFILE"
bash "$HOME/.claude/hooks/auto-push.sh"

exit 0
