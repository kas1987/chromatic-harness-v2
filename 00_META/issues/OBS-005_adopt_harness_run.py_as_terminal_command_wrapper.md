# [OBS-005] Adopt harness_run.py as terminal command wrapper

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P1

## Suggested Owner
Chainbreaker + Auditor

## Objective
Use harness_run.py to capture failed commands, return original exit codes, and auto-log failures.

## Acceptance Checks
- [ ] Failed command creates ERROR_LOG.jsonl entry.
- [ ] Wrapper preserves original command exit code.
- [ ] stderr/stdout excerpt is redacted before logging.
- [ ] Docs include sample usage for npm, python, pytest, and shell commands.

## Labels
`observability`, `p1`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
