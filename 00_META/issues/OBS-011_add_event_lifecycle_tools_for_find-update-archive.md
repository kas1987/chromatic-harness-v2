# [OBS-011] Add event lifecycle tools for find/update/archive

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P2

## Suggested Owner
Archivist

## Objective
Support lookup, status updates, and long-term archival for JSONL event history.

## Acceptance Checks
- [ ] find_event.py can locate an event by event_id.
- [ ] update_event_status.py appends status update records instead of mutating history.
- [ ] Archive policy is documented.
- [ ] Reports compute latest status from appended lifecycle events.

## Labels
`observability`, `p2`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
