# [OBS-012] Create agent mission packet requirement for observability compliance

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P1

## Suggested Owner
Quartermaster + Auditor

## Objective
Ensure every dispatched agent knows how to log, claim files, release files, and halt safely.

## Acceptance Checks
- [ ] Mission packet template includes before/during/after observability actions.
- [ ] Agent handoffs require file claims before mutation.
- [ ] Stop conditions include collision, dirty repo ambiguity, schema validation failure, and secret detection.
- [ ] Acceptance criteria require release of claimed files.

## Labels
`observability`, `p1`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
