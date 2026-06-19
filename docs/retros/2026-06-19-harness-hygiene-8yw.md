# Session Retrospective — Harness Hygiene mc-8yw Batch

**Date:** 2026-06-19
**PRs merged:** none (all changes to ~/.claude/ config files)
**Epics closed:** mc-8yw.1, mc-8yw.2, mc-8yw.3, mc-8yw.4, mc-8yw.5, mc-8yw.6

## What shipped

- **mc-8yw.1 FE-009** — `project_in_review_pipeline.md` updated; review-daemon `disabled: true` is now the authoritative single source of truth, matches `.claude.json` `mcpServers.review-daemon` and `disabledMcpServers` list
- **mc-8yw.2 SC-004** — `audit-logger.sh` deleted from `~/.claude/hooks/`; no callers found in `settings.json` or any hook — was an orphaned file
- **mc-8yw.3 SC-005** — `rpi-preflight.sh` moved from `~/.claude/hooks/` → `~/.claude/bin/`; now a manual tool rather than an orphaned hook
- **mc-8yw.4 SC-008** — Closed as already done; `workstream-registry.yaml` was already present in `governance-federate.sh` FILES array — audit finding was stale
- **mc-8yw.5 SP-009** — `cross-repo-preflight.sh` created at `~/.claude/hooks/`; emits structured JSON to `~/.claude/.agents/events/preflight-events.jsonl` on every skip/fail-open; `CLAUDE_PREFLIGHT_STRICT=1` blocks instead of failing open
- **mc-8yw.6 SP-011** — `governance-federate.sh` now snapshots pre-federate state to `~/.agents/.governance-backup/` and supports `--rollback` subcommand to restore

## Learnings

### 1. Verify federation scripts before acting on audit findings
`workstream-registry.yaml` was already in `governance-federate.sh`'s FILES array — the audit finding (SC-008) was stale. Before acting on any "not federated" finding, grep the federation script for the filename first.

**Action:** `grep <filename> ~/.claude/scripts/governance-federate.sh` before filing or acting on federation gap findings.

### 2. Grep hook filenames in settings.json before any hook work
`audit-logger.sh` had been sitting in `hooks/` with no wiring in `settings.json` for an unknown period. Orphaned hooks accumulate silently because there's no automated check that every file in `hooks/` has a corresponding entry in `settings.json`.

**Action:** When doing hook hygiene, run `grep <hook-filename> ~/.claude/settings.json` first to confirm it's live before investing in fixes.

### 3. Federation/copy scripts need snapshot-before-write
`governance-federate.sh` was overwriting governance YAMLs across 4 roots with no backup. A bad federate (wrong canonical source, partial write) was unrecoverable.

**Action:** Any script that copies files to multiple targets should snapshot the destination state first. Pattern: write to `<dir>/.governance-backup/` keyed by `${root//\//_}__${file}`, then offer `--rollback`.

## Follow-up

- `cross-repo-preflight.sh` exists but is not wired into `settings.json` PreToolUse hooks — the workstream-registry.yaml references it but the hook is not active. Wire or document as manual-only.
- Consider a periodic check: `diff hooks/*.sh` vs what's in `settings.json` hooks to surface orphans before they accumulate.
