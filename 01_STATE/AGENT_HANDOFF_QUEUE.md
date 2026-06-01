# Agent Handoff Queue

Items here are mirrored to GitHub issues via `scripts/sync_queue_to_github.py`.
Format: `- [ ] <bead-id>: <title>` (open) or `- [x] <bead-id>: <title>` (done).

- [x] xacy.1: Install control plane files in chromatic-harness-v2 (Phase 1 pilot)
- [x] xacy.2: Populate KPI scorecard with baseline values
- [x] xacy.3: Enforce P1-P4 classification at session start
- [x] xacy.4: Run 3-5 sessions with GO-mode startup and telemetry logging (Phase 2 SOP)
- [ ] xacy.5: Mirror agent queue to GitHub issues and mutations to PRs (Phase 3)
- [ ] xacy.6: Build Mermaid KPI dashboard and telemetry summaries (Phase 4)

## Observability v2.1 rollout (epic chromatic-harness-v2-trsk -> GitHub #129-140)

Already mirrored to GitHub (#129-140, label `agent-queue`); each issue body carries a `bead:<id>` marker so `sync_queue_to_github.py` matches them as existing (no duplicate creation). Execution order: OBS-001 first (gates the rest).

- [ ] chromatic-harness-v2-trsk.1: [OBS-001] Install Observability v2.1 scaffold
- [ ] chromatic-harness-v2-trsk.2: [OBS-002] Enable file claim/release collision control
- [ ] chromatic-harness-v2-trsk.3: [OBS-003] Enforce schema-backed event validation
- [ ] chromatic-harness-v2-trsk.4: [OBS-004] Route critical/high events to incidents, collisions, and queue items
- [ ] chromatic-harness-v2-trsk.5: [OBS-005] Adopt harness_run.py as terminal command wrapper
- [ ] chromatic-harness-v2-trsk.6: [OBS-006] Add Git state snapshots and last-known-good flow
- [ ] chromatic-harness-v2-trsk.7: [OBS-007] Enable IDE tasks for VS Code/Cursor/Antigravity workflows
- [ ] chromatic-harness-v2-trsk.8: [OBS-008] Enable GitHub Actions observability health check
- [ ] chromatic-harness-v2-trsk.9: [OBS-009] Add secret scan gate to pre-commit and CI
- [ ] chromatic-harness-v2-trsk.10: [OBS-010] Generate recurring observability reports and learning candidates
- [ ] chromatic-harness-v2-trsk.11: [OBS-011] Add event lifecycle tools for find/update/archive
- [ ] chromatic-harness-v2-trsk.12: [OBS-012] Create agent mission packet requirement for observability compliance
