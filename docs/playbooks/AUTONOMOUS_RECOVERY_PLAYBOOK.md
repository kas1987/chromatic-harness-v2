# Autonomous Recovery Playbook

## Purpose
Recover from stale leases, crashed agents, incomplete mutations, and deadlocks.

## Recovery Levels

| Level | Name | Use When |
|---:|---|---|
| R0 | Observe | State unclear, no mutation confirmed |
| R1 | Reclaim | Lease stale but no files changed |
| R2 | Rollback | Partial mutation detected |
| R3 | Verify | Mutation completed but not verified |
| R4 | Human Gate | Destructive/security/unknown impact |

## Stale Lease Recovery

1. Inspect lease.
2. Check heartbeat age.
3. Check associated branch/PR/diff.
4. If no mutation occurred, expire lease.
5. If mutation occurred, route to verifier.
6. Record recovery action.

## Commands

```bash
python scripts/lease_manager.py inspect --stale-only
python scripts/lease_manager.py expire --lease-id <lease_id> --reason "heartbeat stale"
```

## Deadlock Response

1. Freeze new leases for involved resources.
2. Build dependency graph.
3. Identify lowest-priority blocker.
4. Requeue lower-priority task.
5. Release or expire blocked lease.
6. Record incident.
