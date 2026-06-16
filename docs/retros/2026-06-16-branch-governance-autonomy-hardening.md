# Session Retrospective - Branch Governance Autonomy Hardening

**Date:** 2026-06-16
**PRs merged:** none confirmed this session
**Active PR:** #266 (chore(harness): log-retention sweep + CI/branch governance hardening)
**Epics closed:** none confirmed closed this session

## What shipped
- Added startup and audit awareness for branch governance with policy-driven defaults.
- Added autonomy routing for branch governance across local, subagent, and cloud modes.
- Wired branch governance autonomy into weekly CI governance workflows and artifacts.
- Added VS Code task entrypoints for operator execution of local/apply/subagent/cloud modes.
- Ran local autonomy, daily audit, and self-heal loop validations; local path executed successfully.

## Learnings
### 1. Cloud workflow dispatch can fail on default-branch lookup even when workflow files exist on a feature branch
GitHub CLI workflow dispatch returned 404 for workflow filenames not present on the default branch, which can look like a workflow naming bug when it is actually branch visibility.
**Action:** Keep cloud-mode fallback attempts explicit and log all attempted workflow identifiers in artifacts.

### 2. Subagent delegate gate failure should be treated separately from remediation logic failure
Subagent mode halted on pre-swarm gate failure tied to session boot (audit_mcp_context), not branch-governance policy logic.
**Action:** Keep a fallback path and annotate gate failures distinctly in telemetry to avoid false diagnosis.

### 3. Direct Claude fallback on Windows is environment-sensitive
Direct fallback to claude CLI failed with WinError 2 when binary was unavailable on PATH.
**Action:** Detect CLI availability and classify this as environment readiness debt in follow-up tasks.

## KPI snapshot
| KPI | Before | After |
| --- | --- | --- |
| Local branch cap violations | 0 | 0 |
| Remote branch cap violations | 0 | 0 |
| Local stale branches | 9 | 9 |
| Remote stale branches | 7 | 7 |
| Local autonomy dry-run | partial | pass |
| Cloud autonomy dispatch | fail | fail (instrumented fallbacks) |

## Follow-up
- Keep PR #266 open until default-branch workflow visibility and dispatch path are verified in GitHub Actions.
- Resolve delegate gate pre-swarm dependency on audit_mcp_context for subagent mode.
- Ensure claude CLI availability on Windows runners/operators before relying on direct fallback.
- Bead closure check result: `bd list --status in_progress` returned active in-progress items; no blanket closure performed in this post-mortem.
- Next queue review: `bd ready` currently shows 63 ready issues with no active blockers.