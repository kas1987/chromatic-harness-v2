# [OBS-004] Route critical/high events to incidents, collisions, and queue items

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P0

## Suggested Owner
Auditor + Archivist

## Objective
Enable route_event.py so logged events create the correct downstream record.

## Acceptance Checks
- [ ] Critical events append to INCIDENT_LOG.md.
- [ ] file_collision events append to COLLISION_REGISTER.md.
- [ ] medium/high unresolved errors create ERROR_REMEDIATION_QUEUE.md entries.
- [ ] Each downstream record links back to the source event_id.

## Labels
`observability`, `p0`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
