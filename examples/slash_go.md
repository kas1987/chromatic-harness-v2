# Example: `/go`

## Intent

Start the next approved unit of work without letting Claude invent the workflow.

## Adapter Behavior

```bash
# Preferred future command
python scripts/go_mode.py next --from-queue --respect-gates
```

## Required Gates

- queue item exists;
- confidence score recorded;
- lease acquired before mutation;
- verifier required for T3+;
- decision logged.

## Claude Must Not

- pick work outside the queue;
- mutate files without lease;
- skip confidence scoring;
- dispatch hidden agents.
