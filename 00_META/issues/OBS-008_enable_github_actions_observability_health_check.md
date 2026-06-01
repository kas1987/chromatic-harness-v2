# [OBS-008] Enable GitHub Actions observability health check

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P1

## Suggested Owner
Sentinel + Auditor

## Objective
Run validation automatically in CI to prevent observability drift.

## Acceptance Checks
- [ ] .github/workflows/harness-observability-check.yml compiles scripts.
- [ ] Workflow validates starter event log.
- [ ] Workflow runs secret scan.
- [ ] Workflow runs collision detector against active writers.

## Labels
`observability`, `p1`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
