# Lease Playbook

## Execution Loop

```text
Intent -> Manifest -> Lease Request -> Collision Check -> Mutate -> Validate -> Release
```

## Agent Steps

1. Read assigned task.
2. Create mutation manifest.
3. Request lease.
4. Wait for granted status.
5. Mutate only declared resources.
6. Validate.
7. Record evidence.
8. Release lease.

## Lease Acquire Command

```bash
python scripts/lease_manager.py acquire \
  --task-id P0-CC-001 \
  --owner-agent Sentinel \
  --resources scripts/lease_manager.py schemas/lease.schema.json \
  --mode exclusive \
  --risk-tier T3 \
  --ttl-minutes 90 \
  --rollback-plan "revert PR branch"
```

## Lease Release Command

```bash
python scripts/lease_manager.py release --lease-id <lease_id>
```

## Inspect Active Leases

```bash
python scripts/lease_manager.py inspect
```

## Stop Conditions

- Lease denied.
- Resource overlap detected.
- TTL exceeded.
- Heartbeat stale.
- Task scope changes mid-run.
- Agent needs additional files not in manifest.
