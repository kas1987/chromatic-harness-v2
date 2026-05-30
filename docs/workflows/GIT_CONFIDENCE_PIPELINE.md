# Git Confidence Pipeline

Automated commit, review (PR), and merge gated by workflow confidence scores.

**Agent autonomy:** [docs/governance/GIT_AUTONOMY_POLICY.md](../governance/GIT_AUTONOMY_POLICY.md) — agents may run this pipeline without a separate user commit/push request when the plan allows each step.

## Thresholds

| Step | Min score | Requirements |
|------|-----------|--------------|
| Commit | 75 | Verifier approve; staged changes; not critical risk |
| Push | 88 | Commit gate; tests pass; risk not high/critical |
| Open PR | 85 | Push gate; not on main/master |
| Merge | 95 | PR gate; CI green; low risk only |

## Commands

```bash
# Dry-run: see what would run
python scripts/workflow_git.py plan --confidence 92 --verifier approve --tests-passed

# After GO VERIFY (reads confidence from run log)
python scripts/workflow_git.py ship --from-log --verifier approve --run-tests

# Execute allowed steps
python scripts/workflow_git.py ship --execute --confidence 95 --verifier approve --tests-passed

# Full GO ship (runs tests + dry-run ship)
python scripts/workflow_go.py "GO SHIP"
```

## Safety

- Default is **dry-run**; pass `--execute` to run git/gh.
- Secrets in changed paths (`.env`, keys) block all steps.
- `PUSH_MERGE_DEPLOY` legacy action still requires human unless using git pipeline.
