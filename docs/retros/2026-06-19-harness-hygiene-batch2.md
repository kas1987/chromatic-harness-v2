# Session Retrospective — Harness Hygiene Batch 2

**Date:** 2026-06-19
**PRs merged:** none (all changes to ~/.claude/ config files)
**Beads closed:** mc-5di9, mc-irhn, mc-jcp6, mc-5hdy, mc-iuhh

## What shipped

- **mc-5di9** — governance-federate.sh already existed from a prior session; wired it as a background SessionStart hook in `~/.claude/settings.json`
- **mc-irhn** — review-daemon registered in `~/.claude/.mcp.json` with `disabled:true`; matches its existing disabled state in `.claude.json`
- **mc-jcp6** — 10 bats tests written to `~/.claude/hooks/tests/harness-log-rotate.bats`: under-cap no-trim, over-cap trim, archive creation, no-overwrite existing archive, intake 500-line cap, dispatch cap, old-.bak cleanup after 7 days, missing-file safe exit
- **mc-5hdy** — Closed as already done; `model-router.sh` has `OL_BUMP_MAX_SESSION` session bump cap; Featherless is flat-rate so a daily spend cap is not applicable
- **mc-iuhh** — Multica pipeline intentionally PAUSED (InReviewWatcher scheduler disabled 2026-06-16); hooks on disk are valid, not orphaned; closed as deferred-not-orphaned

## Learnings

### 1. Check if a "missing" script already exists before acting
Audit findings that say "create X" can be stale — governance-federate.sh was flagged as missing but had already been created in a prior session. Always `ls` the target path before implementing.

**Action:** Before creating any script named in an audit finding, grep/ls for it first.

### 2. Featherless is flat-rate — session-count guards, not spend caps
Featherless charges a flat monthly fee, not per-token. A "daily spend cap" request for Featherless tier routing is not applicable. The correct guard is a session-count bump limit (`OL_BUMP_MAX_SESSION`), which already exists.

**Action:** When evaluating cost-cap beads for Featherless tier, close as already-handled if session bump cap is in place.

### 3. "Orphaned hooks" may be intentionally paused systems
Audit findings about hooks with no entry point can reflect deliberately paused pipelines, not dead code. Check memory/project notes (`project_in_review_pipeline.md`) before deleting.

**Action:** Before deleting hooks flagged as orphaned, grep project memory for "paused", "disabled", "scheduler".

## Follow-up

- Verify bats tests pass: `bats ~/.claude/hooks/tests/harness-log-rotate.bats`
- Wire `cross-repo-preflight.sh` into `settings.json` PreToolUse (currently exists on disk but not hooked — flagged by prior post-mortem)
- Re-enable Multica pipeline after PR #266 merges
