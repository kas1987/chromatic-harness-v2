# [OBS-010] Generate recurring observability reports and learning candidates

## Target Repo
`kas1987/prism-autonomy-harness` or active v2 Harness successor repo.

## Priority
P2

## Suggested Owner
Archivist + Auditor

## Objective
Turn raw event history into reports, repeated-error summaries, and playbook learning candidates.

## Acceptance Checks
- [ ] generate_observability_report.py writes a dated markdown report.
- [ ] propose_learnings.py identifies repeated error signatures.
- [ ] Report includes unresolved high/critical events, repeated signatures, noisy files, and recommended next work.
- [ ] Learning candidates are appended to LEARNINGS_LOG.md or staged for review.

## Labels
`observability`, `p2`, `v2.1`, `harness`

## Dispatch Notes
This issue should be treated as agent-dispatchable next work. Do not expand scope without updating acceptance checks.
