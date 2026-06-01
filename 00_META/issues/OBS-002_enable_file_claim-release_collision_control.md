# [OBS-002] Enable file claim/release collision control

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P0

## Suggested Owner
Auditor + Sentinel

## Objective
Wire claim_files.py and release_files.py into agent and IDE workflows so multiple writers cannot silently edit the same file.

## Acceptance Checks
- [ ] First writer can claim one or more files.
- [ ] Second writer claiming same file receives non-zero exit code.
- [ ] Collision is logged and routed to COLLISION_REGISTER.md.
- [ ] Release clears active writer entries.

## Labels
`observability`, `p0`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
