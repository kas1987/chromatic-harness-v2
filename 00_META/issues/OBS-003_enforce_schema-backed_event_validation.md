# [OBS-003] Enforce schema-backed event validation

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P0

## Suggested Owner
Auditor

## Objective
Make validate_event_schema.py the required validator for ERROR_LOG.jsonl and CI checks.

## Acceptance Checks
- [ ] Invalid severity, status, category, or event_type fails validation.
- [ ] Missing source metadata fails validation.
- [ ] Malformed JSONL exits non-zero.
- [ ] Validation command is documented in QUICKSTART.md.

## Labels
`observability`, `p0`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
