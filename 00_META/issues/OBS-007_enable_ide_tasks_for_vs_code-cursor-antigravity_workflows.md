# [OBS-007] Enable IDE tasks for VS Code/Cursor/Antigravity workflows

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P1

## Suggested Owner
Cartographer + Auditor

## Objective
Make observability actions accessible through IDE tasks so logging and validation are low-friction.

## Acceptance Checks
- [ ] .vscode/tasks.json includes validate logs, detect collisions, snapshot git, and summarize errors.
- [ ] docs/IDE_SETUP.md explains how to run each task.
- [ ] Tasks do not assume platform-specific shell features where avoidable.

## Labels
`observability`, `p1`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
