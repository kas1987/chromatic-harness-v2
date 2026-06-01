# Example: `/audit`

## Intent

Show current harness health and governance readiness.

## Adapter Behavior

```bash
python scripts/harness_health_check.py --markdown
python scripts/drift_gate.py
python scripts/release_readiness.py
```

## Claude Must Not

- reinterpret warnings as approval;
- promote a release;
- invent missing artifacts.
