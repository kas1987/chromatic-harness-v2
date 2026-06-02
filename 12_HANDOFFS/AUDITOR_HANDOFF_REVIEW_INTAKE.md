# Agent Handoff: Auditor - Review Intake Validation

## Task ID
NW-REVIEW-INTAKE-001

## Mission
Validate that GitHub review events are converted into normalized findings and queue items.

## Allowed Files
- `.github/workflows/review-intake.yml`
- `scripts/review_intake.py`
- `scripts/classify_review_finding.py`
- `schemas/*.schema.json`
- `07_LOGS_AND_AUDIT/review_intake/findings.jsonl`
- `07_LOGS_AND_AUDIT/review_intake/queue.json`

## Blocked Actions
- Do not push auto-fixes to PR branches.
- Do not edit production deployment files.
- Do not change secrets or permissions beyond documented workflow permissions.

## Acceptance Criteria
- Sample event creates one finding.
- Same event does not duplicate queue item.
- Low-confidence/vague comments are not marked ready for mutation.
- Output remains valid JSON/JSONL.

## Stop Conditions
- Event payload shape is unknown.
- Queue file is malformed.
- Action permissions fail.
