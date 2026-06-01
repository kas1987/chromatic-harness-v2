# Example: `/ship`

## Intent

Use the confidence-gated git pipeline.

## Adapter Behavior

```bash
python scripts/workflow_git.py plan --from-log
python scripts/workflow_git.py ship --from-log --execute
```

## Required Gates

- confidence;
- verifier approval;
- tests;
- collision check;
- CI governance.

## Claude Must Not

- direct merge;
- skip tests;
- skip verifier;
- force collision without human approval.
