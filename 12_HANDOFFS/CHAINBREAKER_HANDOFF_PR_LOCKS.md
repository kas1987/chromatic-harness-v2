# Agent Handoff: Chainbreaker - PR Branch Locking

## Task ID
NW-REVIEW-INTAKE-002

## Mission
Enforce one active mutating agent per PR branch.

## Allowed Files
- `scripts/lock_pr_branch.py`
- `schemas/pr_branch_lock.schema.json`
- `04_PLAYBOOKS/PR_COLLISION_CONTROL_PLAYBOOK.md`
- `07_LOGS_AND_AUDIT/review_intake/locks/*.lock.json`

## Acceptance Criteria
- Lock acquire succeeds when no active lock exists.
- Second acquire fails while lock is active.
- Expired lock can be replaced.
- Release removes lock.

## Stop Conditions
- Time parsing fails.
- Lock files cannot be written.
- Agent needs central DB lock instead of repo-local file lock.
