# [OBS-001] Install Observability v2.1 scaffold

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P0

## Suggested Owner
Janitor + Auditor

## Objective
Install the v2.1 scaffold into the Harness repo, preserving existing files and verifying source-of-truth paths.

## Acceptance Checks
- [ ] Repo contains PDR, observability docs, schema, scripts, queues, IDE tasks, CI workflow, and manifest.
- [ ] No existing repo-owned files are overwritten without review.
- [ ] python -m py_compile scripts/*.py passes.
- [ ] Starter ERROR_LOG.jsonl validates.

## Labels
`observability`, `p0`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
