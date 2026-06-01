# Integration Guide

## Terminal Integration

Wrap important commands with logging on failure:

```bash
npm run build || python scripts/log_harness_event.py \
  --source terminal \
  --event-type error \
  --severity medium \
  --category test_failure \
  --message "npm run build failed" \
  --command "npm run build" \
  --status open
```

## IDE Integration

Add IDE tasks that call `log_harness_event.py` after failed builds, tests, or generation runs.

## Agent Integration

Every agent mission should include:

- Assigned task
- Allowed files
- Forbidden files
- Expected logging behavior
- Stop conditions
- Collision behavior

## Git Hook Integration

Potential future hooks:

- pre-commit: validate event log
- pre-commit: detect likely secrets
- pre-push: summarize unresolved high/critical events
- post-merge: log merge/collision events

## CI Integration

CI can append events for:

- Failed tests
- Failed builds
- Broken schema validation
- Missing docs
- Security scans
