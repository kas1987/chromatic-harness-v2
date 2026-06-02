# Implementation Notes

## Start here

1. Ensure schemas, scripts, and workflow are committed.
2. Open a PR with review-intake files.
3. Add an inline review comment.
4. Confirm `07_LOGS_AND_AUDIT/review_intake/findings.jsonl` and `queue.json` update.

## Suggested promotion path

- Week 1: passive intake only.
- Week 2: queue creation and dispatch packets.
- Week 3: local agent patching with branch locks.
- Week 4: PR resolution comments.
- Later: central GitHub App and SQLite dashboard.

## Human gates

Require human approval for:

- secrets or credentials
- auth/permissions
- production deployment
- architecture rewrites
- deleting files or branches
- cross-repo mutation
