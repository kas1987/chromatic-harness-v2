#!/usr/bin/env bash
# Polls Multica for issues in in_review status and triggers tiered LLM review.
# Called by: multica autopilot (cron every 2 min) OR manual invocation.

MULTICA_BIN="$HOME/.multica/bin/multica"
REVIEW_LOG="$HOME/.claude/.agents/review/watcher.log"
REVIEWED_CACHE="$HOME/.claude/.agents/review/reviewed-ids.txt"

mkdir -p "$(dirname "$REVIEW_LOG")" "$(dirname "$REVIEWED_CACHE")"
touch "$REVIEWED_CACHE"

# Get all in_review issues as JSON
IN_REVIEW_JSON=$("$MULTICA_BIN" issue list --status in_review --output json 2>/dev/null) || exit 0
[ -z "$IN_REVIEW_JSON" ] && exit 0

# Parse JSON with jq: output id<TAB>title per line
PAIRS=$(echo "$IN_REVIEW_JSON" | jq -r '.issues[] | .id + "\t" + .title' 2>/dev/null)
[ -z "$PAIRS" ] && exit 0

echo "$PAIRS" | while IFS=$'\t' read -r id title; do
  [ -z "$id" ] && continue
  # Skip already-reviewed issues (cache written only on successful dispatch)
  grep -qF "$id" "$REVIEWED_CACHE" && continue
  echo "[watcher $(date -Iseconds)] Triggering review for $id: $title" | tee -a "$REVIEW_LOG"
  MULTICA_ISSUE_ID="$id" MULTICA_ISSUE_TITLE="$title" \
    bash "$HOME/.claude/hooks/review-dispatch.sh" "$id"
  if [ $? -eq 0 ]; then
    echo "$id" >> "$REVIEWED_CACHE"
  else
    echo "[watcher] dispatch failed for $id — will retry next poll" | tee -a "$REVIEW_LOG"
  fi
done

exit 0
