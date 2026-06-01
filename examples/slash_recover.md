# Example: `/recover`

## Intent

Inspect failed, stalled, or duplicate work safely.

## Adapter Behavior

```bash
python scripts/harness_health_check.py --markdown
python scripts/lease_manager.py summarize
python scripts/lease_manager.py inspect --active-only
```

Mutation is not default. Expiring a lease requires evidence and human approval.
