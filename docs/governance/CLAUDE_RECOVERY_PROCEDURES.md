# Claude Recovery Procedures

## Purpose

Define safe Claude-assisted recovery behavior when autonomous harness work fails, stalls, collides, or creates duplicate artifacts.

## Recovery Modes

### 1. Inspect Only

Default mode. Safe for `/recover`.

Allowed:

```bash
python scripts/harness_health_check.py --markdown
python scripts/lease_manager.py summarize
python scripts/lease_manager.py inspect --active-only
python scripts/workflow_git.py plan --from-log
```

### 2. Stale Lease Recovery

Allowed only when a lease is expired or owner is absent.

Required evidence:

- lease ID;
- owner agent;
- resource list;
- expiry time;
- reason for recovery;
- rollback note.

Command pattern:

```bash
python scripts/lease_manager.py expire --lease-id <id> --reason "stale owner / human approved"
```

### 3. Duplicate Issue Recovery

Allowed if two issues have the same title/body and one is clearly duplicate.

Procedure:

1. identify canonical issue;
2. comment on duplicate referencing canonical issue;
3. close duplicate as not planned or duplicate;
4. update queue references if needed.

### 4. Failed Ship Recovery

Allowed:

- inspect workflow logs;
- run `workflow_git.py plan`;
- create remediation issue;
- ask for human approval if force/collision override is requested.

Not allowed:

- force push without human approval;
- merge while CI is red;
- skip verifier gate.

## Recovery Stop Conditions

Stop if:

- state is ambiguous;
- lease is active and owner may still be working;
- failure affects secrets;
- data loss risk exists;
- rollback plan is missing;
- recovery requires deleting files/branches.
