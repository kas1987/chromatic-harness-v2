# [OBS-009] Add secret scan gate to pre-commit and CI

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P1

## Suggested Owner
Sentinel

## Objective
Prevent secrets from entering logs, docs, scripts, or generated artifacts.

## Acceptance Checks
- [ ] scan_for_secrets.py detects fake OpenAI-style tokens.
- [ ] pre-commit hook blocks detected secrets.
- [ ] CI fails on detected secrets.
- [ ] Docs explain safe false-positive handling.

## Labels
`observability`, `p1`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
