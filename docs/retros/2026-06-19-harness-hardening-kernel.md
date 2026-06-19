# Session Retrospective — Harness Hardening & Kernel Definition

**Date:** 2026-06-19
**PRs merged:** none (compiled JS + docs only)
**Beads closed:** mc-6a5.1, mc-6nal

## What shipped

- **mc-6a5.1** — Governance header check in `review-daemon/dist/reviewers/mechanical.js`: T2 grep for `## GOVERNANCE CONSTRAINTS` in `.md`/`.txt` worker outputs. WARN-only (`passed: true` always, `warn: true` flag). `review_run.js` surfaces warns array with `worker_id`, `task_id`, `result_path` in the mechanical result block.
- **mc-6nal** — `docs/architecture/HARNESS_KERNEL.md` created: 5-tier matrix (Nano/Lite/Core/Cloud/Fleet), mandatory vs optional subsystems, bloat audit criteria, local-first execution rules, cloud escalation policy, graceful degradation chain, memory compression strategy, mobile-safe telemetry/logging, minimal command/runtime schema.

## Learnings

### 1. review-daemon has no source — only dist/
The `~/.claude/review-daemon/` directory contains only `dist/` and `node_modules/` — no `src/`. All changes must be made directly to compiled JS. This creates drift risk: changes will be overwritten if the daemon is ever rebuilt from original source.

**Action:** Before any future review-daemon work, check whether source has been restored. Add a note to review-daemon README (or create one) flagging this. Track source recovery as a separate bead.

### 2. New compliance checks should start at WARN, not BLOCK
The governance header check uses `passed: true` always so it never blocks review. This is correct: enforcement should be `WARN → 100% adoption → BLOCK`. Jumping straight to BLOCK on a new check causes false failures before the codebase has been updated.

**Action:** Apply this pattern to all new mechanical checks: introduce as WARN, graduate to BLOCK via explicit bead after adoption is confirmed.

## Follow-up

- Create bead to restore review-daemon source (recover src/ from git history or upstream)
- Wire `cross-repo-preflight.sh` into `settings.json` PreToolUse (flagged in prior retro, still open)
- Graduate `governance-header` check from WARN → BLOCK after adoption reaches 100%
