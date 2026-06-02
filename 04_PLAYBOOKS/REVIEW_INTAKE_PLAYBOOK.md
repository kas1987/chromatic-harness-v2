# Review Intake Playbook

## Purpose

Convert GitHub PR review events into normalized, auditable review findings.

## Inputs

- GitHub webhook or GitHub Actions event payload
- Repository full name
- Pull request number, when available
- Review/comment/check metadata

## Outputs

- `07_LOGS_AND_AUDIT/review_intake/findings.jsonl`
- `07_LOGS_AND_AUDIT/review_intake/queue.json`
- `07_LOGS_AND_AUDIT/review_intake/state.json`

## Operating Loop

```text
Receive Event -> Normalize -> Classify -> Score -> Dedupe -> Queue -> Log State
```

## Rules

1. Do not patch code during passive intake.
2. Do not create queue items for successful checks or approved reviews.
3. Every actionable item must get a dedupe key.
4. Low-confidence findings must be blocked or review-required.
5. Security and architecture findings need stronger gates.

## Stop Conditions

- Payload cannot be parsed.
- Repo or PR cannot be identified.
- Finding lacks body/evidence.
- Queue file is malformed.
