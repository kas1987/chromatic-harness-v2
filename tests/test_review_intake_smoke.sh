#!/usr/bin/env bash
set -euo pipefail

# Smoke test for review_intake.py
# Run from repo root: bash tests/test_review_intake_smoke.sh

SCRIPT="scripts/review_intake.py"
EVENT="tests/fixtures/review_intake/sample_pull_request_review_comment_event.json"
BASE="07_LOGS_AND_AUDIT/review_intake"

# Clean previous test artifacts
rm -f "$BASE/findings.jsonl" "$BASE/queue.json" "$BASE/state.json"

# Run intake
python "$SCRIPT" \
  --event-name pull_request_review_comment \
  --event-path "$EVENT" \
  --findings "$BASE/findings.jsonl" \
  --queue "$BASE/queue.json" \
  --state "$BASE/state.json"

# Assert findings file has one record
COUNT=$(wc -l < "$BASE/findings.jsonl" | tr -d ' ')
if [ "$COUNT" -ne 1 ]; then
  echo "FAIL: expected 1 finding, got $COUNT"
  exit 1
fi

# Assert queue file exists and has items
if ! python -c "import json,sys; d=json.load(open('$BASE/queue.json')); assert len(d['items'])==1; print('queue ok')"; then
  echo "FAIL: queue validation failed"
  exit 1
fi

# Assert state file exists
if [ ! -f "$BASE/state.json" ]; then
  echo "FAIL: state file missing"
  exit 1
fi

# Run again with same event → should dedupe and not create duplicate
python "$SCRIPT" \
  --event-name pull_request_review_comment \
  --event-path "$EVENT" \
  --findings "$BASE/findings.jsonl" \
  --queue "$BASE/queue.json" \
  --state "$BASE/state.json"

COUNT2=$(wc -l < "$BASE/findings.jsonl" | tr -d ' ')
if [ "$COUNT2" -ne 1 ]; then
  echo "FAIL: expected 1 finding after dedupe, got $COUNT2"
  exit 1
fi

echo "PASS: review_intake smoke test"
