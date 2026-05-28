#!/usr/bin/env bash
# Stop hook: warn if a Chronicle was started but never completed.
# Fires on every session Stop. Advisory only — does not block.

CHRON="${PWD}/.agents/chronicle"

[ -f "$CHRON/events.jsonl" ] || exit 0
[ ! -f "$CHRON/complete.json" ] || exit 0   # complete — all good

# events.jsonl present, complete.json absent → interrupted Chronicle
EPIC_ID=$(jq -r 'select(.event=="discovery_complete") | .epic_id' \
  "$CHRON/events.jsonl" 2>/dev/null | tail -1)

if [ -n "$EPIC_ID" ] && [ "$EPIC_ID" != "null" ]; then
  echo "WARN: Chronicle for epic $EPIC_ID is incomplete (no complete.json)."
  echo "      Re-run: /post-mortem $EPIC_ID"
else
  # No discovery_complete yet — very early interruption
  GOAL=$(jq -r 'select(.event=="rpi_start") | .goal' \
    "$CHRON/events.jsonl" 2>/dev/null | tail -1)
  echo "WARN: Chronicle interrupted before discovery_complete."
  [ -n "$GOAL" ] && echo "      Goal was: $GOAL"
  echo "      Re-run: /rpi (check .agents/chronicle/events.jsonl for context)"
fi
