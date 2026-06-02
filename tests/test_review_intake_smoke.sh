#!/usr/bin/env bash
set -euo pipefail

# End-to-end smoke for the review-intake pipeline.
# Runs every event fixture through intake, proves dedupe + synchronize invalidation,
# then dispatches a ready item. Uses a throwaway BASE so tracked repo state is untouched.
# Run from repo root: bash tests/test_review_intake_smoke.sh

FIX="tests/fixtures/review_intake"
BASE="$(mktemp -d)"
trap 'rm -rf "$BASE"' EXIT

run_intake() {
  python scripts/review_intake.py \
    --event-name "$1" --event-path "$FIX/$2" \
    --findings "$BASE/findings.jsonl" --queue "$BASE/queue.json" --state "$BASE/state.json"
}

run_intake pull_request_review_comment sample_pull_request_review_comment_event.json
run_intake pull_request_review        sample_pull_request_review_event.json
run_intake issue_comment              sample_issue_comment_event.json
run_intake check_run                  sample_check_run_event.json
run_intake workflow_run               sample_workflow_run_event.json

# Dedupe: re-running the first event must not add a second finding.
run_intake pull_request_review_comment sample_pull_request_review_comment_event.json

python - "$BASE" <<'PY'
import json, sys
from pathlib import Path
base = Path(sys.argv[1])
findings = [json.loads(l) for l in (base/"findings.jsonl").read_text().splitlines() if l.strip()]
sources = {f["source"] for f in findings}
expected = {"github_pr_review_comment", "github_pr_review", "github_issue_comment", "github_check_run", "github_workflow_run"}
assert expected <= sources, f"missing sources: {expected - sources}"
# dedupe: pr_review_comment fixture appears once despite two runs
assert sum(1 for f in findings if f["source"] == "github_pr_review_comment") == 1, "dedupe failed"
print(f"intake ok: {len(findings)} findings across {len(sources)} sources")
PY

# Synchronize invalidation on PR #42.
run_intake pull_request sample_pull_request_synchronize_event.json

# Dispatch one ready item (PR-level review-comment finding is ready).
python scripts/dispatch_review_work.py \
  --queue "$BASE/queue.json" --lock-dir "$BASE/locks" \
  --packet-dir "$BASE/mission_packets" --dispatch-log "$BASE/dispatch_log.jsonl" --limit 1 >/dev/null

test -s "$BASE/dispatch_log.jsonl" || { echo "FAIL: no dispatch record written"; exit 1; }

echo "PASS: review_intake end-to-end smoke (5 sources, dedupe, synchronize, dispatch)"
