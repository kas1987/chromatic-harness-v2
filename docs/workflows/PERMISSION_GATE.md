# Permission Gate

## Purpose

Prevent dynamic workflows from turning into unbounded or unsafe autonomy.

## Rules

| Action | Permission |
|---|---|
| Read assigned files | Allowed |
| Read unrelated files | Requires justification |
| Edit assigned files | Allowed if confidence >= 75 |
| Edit unassigned files | Halt |
| Delete files | Human approval required |
| Rename major folders | Human approval required |
| Change build/config/deployment | Human approval required |
| Touch secrets/env/auth | Halt |
| Run tests | Allowed |
| Install packages | Human approval required |
| Push/merge/deploy | Human approval required unless confidence gates pass (see below) |

## Confidence-gated git (auto commit / review / merge)

When `workflow_git.py` is used, push/merge may proceed **without manual approval** only if all gates pass:

| Step | Min confidence | Other gates |
|------|---------------|-------------|
| **Commit** | 75 | Verifier approve; non-critical risk |
| **Push** | 88 | Tests pass; risk not high/critical |
| **Open PR** | 85 | Push gate passed; not on main/master |
| **Merge** | 95 | CI green; low risk only |

CLI: `python scripts/workflow_git.py plan` (dry-run) → `ship --execute` when allowed.

`PUSH_MERGE_DEPLOY` via legacy permission API still requires human unless using the git pipeline actions (`GIT_COMMIT`, `GIT_PUSH`, `GIT_PR_REVIEW`, `GIT_MERGE`).

## Hard Stops

The agent must stop if:

- the task requires credentials
- destructive action is needed
- production systems are affected
- files outside allowed scope must be changed
- confidence is below required threshold
