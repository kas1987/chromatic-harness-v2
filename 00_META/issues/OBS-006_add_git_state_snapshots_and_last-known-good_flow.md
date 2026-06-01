# [OBS-006] Add Git state snapshots and last-known-good flow

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P1

## Suggested Owner
Auditor + Janitor

## Objective
Capture branch, commit, dirty state, staged files, modified files, and untracked files before/after agent work.

## Acceptance Checks
- [ ] snapshot_git_state.py outputs branch, commit, dirty state, and changed files.
- [ ] check_dirty_state.py exits non-zero when repo is dirty if strict mode is enabled.
- [ ] update_last_known_good.py records a clean validated checkpoint.
- [ ] Incident records can reference latest snapshot.

## Labels
`observability`, `p1`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
