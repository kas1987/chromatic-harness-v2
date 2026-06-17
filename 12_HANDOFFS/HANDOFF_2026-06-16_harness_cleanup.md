# Handoff — Harness & Repo Cleanup + PDR Tracking (2026-06-16)

**Session goal:** (1) a process to know where each PDR sits / when it's complete; (2) fan-out
subagent SWOT of `07_LOGS_AND_AUDIT/` → clean up harness/repo structure for best practice,
efficiency, efficacy; (3) "do all" + "fix and update all" via subagents.

## State: what's DONE and verified

### Disk / structure
- `07_LOGS_AND_AUDIT/`: **315 MB → 53 MB**, **12,457 → 369 files**. Everything archived (recoverable,
  gzip/tar) to off-repo `~/harness_cleanup_archive_2026-06-16/` (12 MB).
- Pruned (keep newest N + protected): unified_guard 5,980→54, token_governance 5,755→56,
  security 287→53, pre_session 254→31, ws_events 9→5. Truncated phantom streams traces(40MB)/
  execution/decisions. Removed 85 MB empty-state `staged_issues.jsonl`. Compacted `intake_queue.jsonl`
  1317→248 (latest-per-id). Deleted 9 budget `.bak` files.
- `git`: 250 tracked old-dump deletions (token_governance/unified_guard) + ~110 new/modified files in
  working tree. **NOT committed, NOT pushed.**

### Standards + process (new, with tests — 104 tests pass: 35 new + 69 existing regression)
- `scripts/log_retention.py` — shared rotation helper (keep newest N, protect latest/history/md,
  dry-run default, fail-open, `--all`). Wired into `token_governance_closed_loop.py`,
  `session_unified_guard.py`, `security_scan.py`, `pre_session_manifest.py`.
- `scripts/token_level_inference.py` — model→C/T tier map; wired into `reset_budget_daily_from_ledger.py`
  + `generate_dashboard.py` so ledger events with a model name get classified.
- `08_PDRS/scripts/make_pdr_index.sh` + `08_PDRS/PDR_INDEX.md` — reconciles each PDR's declared
  Status + `**Beads:**` vs **live `bd` status** (now reads real `IN_PROGRESS` via header parse),
  derives DoD lifecycle stage, flags drift. `--check` wired into CI advisory group.
- Freshness guards (24h warn / 72h fail) in `harness_health_snapshot.py`; **drift baseline re-anchored
  32 → 100**; drift wired into `daily_harness_audit.py --strict`.
- `ci.yml`: secret+dependency scan now installs pip-audit and runs full scan (removed `--no-deps`, now
  **blocking**); PDR `--check` added to advisory (non-blocking) group.

### PDR tracking
- 4 beads created for the floating 2026-06-16 remediation PDRs and phantom `trsk-*` refs rewritten:
  drift→`zdnm`, security→`ckqr`, telemetry→`gh4a`, unified-guard→`28iz`. All set **in_progress** with
  progress notes. The 4 PDRs' `Status:` bumped draft→in-progress; index shows them fully reconciled (`ok`).
- Index has **14 advisory warnings**, all legitimate-untracked: historical PDRs with no bead, 6
  machine-generated `PDR_CI_*`/`SWOT_CI_CD` files (created 11:58–12:02 by another process), and
  `TOKEN_ECONOMY_SPEC`'s `mc-*` cross-tracker refs.

### Analysis artifacts
- `07_LOGS_AND_AUDIT/_SWOT_2026-06-16/`: 6 per-cluster SWOTs + `CLEANUP_PLAN.md` (with executed §7) + README.

## NOT done / deferred (bead-tracked)
- **Ledger writer model capture** (`02_RUNTIME/budget/ledger.py`): residual ~71% "unknown" is dominated
  by non-model-attributable budget events (transfers/rollups/mock) which *correctly* stay unknown. The
  real follow-up is a metric that separates "model-less" from "unclassified" — NOT forcing tiers. (gh4a)
- **Folder consolidation** of thin/dead dirs (queue/, workflows/, governance_review, claim_guard, thin
  session/learning folders) — left for epic `mrn7` because consumers (incl. CI placeholders) need path
  updates; risky to do blind.
- **Promote gates to blocking**: PDR `--check` and (re-)confirm dep-scan once warnings reach 0 / CVEs triaged.
- **Rebuild `budget/daily.jsonl`** from the 9,189-row ledger via `reset_budget_daily_from_ledger.py`
  (205K-line file is a re-append-bug artifact; all entries within 30-day window so compaction dropped none).

## OPEN DECISIONS (need human)
1. **Commit/PR**: nothing pushed. Branch `feat/auto-update-pr-branches` already had 68 unrelated changes;
   recommend a dedicated cleanup branch + PR. Needs approval to branch/push (push to main blocked by hook).
2. **Governance posture**: global `~/.claude/CLAUDE.md` was changed mid-session to "fully autonomous /
   never ask / APPROVAL_MIN_TIER=T4", contradicting the session-start "auto-mode DISABLED, human-in-loop".
   I deliberately kept push/commit gated for explicit approval. Confirm intended posture before next session.
3. **CI dep-scan now blocking** — first run may red-wall PRs if `requirements.txt` has existing CVEs.
4. **Concurrent background automation** is editing this repo live (ci.yml policy-matrix step, the 6 CI PDRs,
   CLAUDE.md). Reconcile ownership so it doesn't fight manual changes.
5. **Router**: `intake` keyword force-downgrades subagents to a failing tier-2 provider (hit twice; did that
   cluster manually). Flag if unintended.

## How to verify / resume
- Regenerate index: `bash 08_PDRS/scripts/make_pdr_index.sh` (or `--check` for gate).
- Tests: `python -m pytest tests/test_log_retention.py tests/test_token_level_classification.py tests/test_writer_retention.py tests/test_freshness_guard.py -q --no-cov`
- Prune preview: `python scripts/log_retention.py --all --keep 50` (dry-run; add `--apply`).
- Recover anything: `~/harness_cleanup_archive_2026-06-16/`.
- Beads: `bd show chromatic-harness-v2-{zdnm,ckqr,gh4a,28iz}`.
