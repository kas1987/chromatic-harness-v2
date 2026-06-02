# PR Collision Control Playbook

## Purpose

Prevent multiple agents, IDEs, or terminals from mutating the same PR branch at the same time.

## Core Rule

One PR branch equals one active mutating agent.

## Lock Lifecycle

```text
Acquire -> Patch -> Validate -> Comment -> Release
```

## Lock Fields

- lock_id
- repo
- pr_number
- branch
- holder
- queue_item_id
- started_at
- expires_at

## Behavior

- Read-only inspection does not require a lock.
- Write/push/commit requires a lock.
- Expired locks may be replaced.
- Active locks block new mutation work.

## Stop Conditions

- Lock cannot be acquired.
- Branch changed unexpectedly.
- Agent needs to edit files outside allowed scope.

## Tooling

Use `scripts/lock_pr_branch.py`:

```bash
# Acquire
python scripts/lock_pr_branch.py acquire --repo owner/repo --pr-number 42 --holder Sentinel --queue-item-id NW-1 --ttl-minutes 30

# Status
python scripts/lock_pr_branch.py status --repo owner/repo --pr-number 42

# Release
python scripts/lock_pr_branch.py release --repo owner/repo --pr-number 42
```

Lock files are stored in `07_LOGS_AND_AUDIT/review_intake/locks/`.
