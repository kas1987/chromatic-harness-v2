# Session Retrospective — Playbook Evolution Feedback Loop

**Date:** 2026-06-02
**PRs merged:** #197
**Beads closed:** `chromatic-harness-v2-7d2.5` (P3 — Playbook evolution feedback loop)
**Base:** `3ab50a6` → `84d58f3`

## What shipped

- **`scripts/propose_playbook_evolution.py`** — the missing P3 #12 feedback arrow from the gaps doc. A read-only aggregator over `07_LOGS_AND_AUDIT/decisions/decision_log.jsonl` that mines three recurring-signal families — `codify_lesson` (recurring `lesson` text), `tune_gate` (low/medium-band escalations), `add_fix_pattern` (clustered failure `reason`) — routes each to the most relevant `04_PLAYBOOKS/` doc, and appends **proposals only** to staging (`00_META/observability/PLAYBOOK_EVOLUTION_PROPOSALS.md` + `.jsonl`). It never edits a playbook.
- **`tests/test_propose_playbook_evolution.py`** — 13 unit tests: routing + fallback, threshold gating, noise filter, torn-line tolerance, window-tail, end-to-end staging, dry-run.
- **`docs/workflows/PLAYBOOK_EVOLUTION_FEEDBACK_LOOP.md`** — usage + mandatory human-gate doc.

## Learnings

### 1. The gaps doc was stale on preconditions — verify against the live repo, not the doc
The research doc marked Decision Log (P0) and Agent Lead (P2) as "Not started," and listed 7d2.5 as blocked on them. In reality `decision_log.jsonl` (4.9 MB) and `execution.jsonl` (16.9 MB) were already populated and `decision_magnet.py` existed. **Action:** before un-deferring a dependency-gated bead, check the filesystem/data, not the design doc's status column.

### 2. Decision-log `reason` is `error or next` → command-shaped noise
`two_log.py::append_decision` sources `reason` from `workflow_entry.get("error") or workflow_entry.get("next", "")`, so on a non-error step the `reason` is a routine navigation command (`bd show <id>`). Live data had a `bd show …` cluster at 1197×. Un-filtered, fix-pattern mining drowns in inspection commands. **Action:** any decision-log miner must noise-filter command-shaped reasons (`bd show`/`git`/`gh`/…). Captured in `bd remember`.

### 3. Live dry-run before committing the heuristic
Running `--dry-run` against the real 4.9 MB log (not just unit fixtures) is what surfaced the noise problem and a genuine signal (1804 medium-band replans). Synthetic tests alone would have shipped the noisy version. **Action:** smoke-test data-mining scripts against production data before finalizing thresholds/filters.

### 4. Route only to playbooks that exist at the build base
The worktree base (`3ab50a6`) had 8 playbooks; `REVIEW_*`/`PR_COLLISION` live only on the epic branch. The routing table was trimmed to the 8 base-existing playbooks so proposals don't reference nonexistent files. **Action:** validate label targets against the actual base tree, not the main checkout.

## KPI snapshot

| Metric | Value |
|---|---|
| PRs | 1 (#197) |
| CI result | BOTH_GREEN first try (0 failures) |
| Tests added | 13 |
| Net lines | +449 |
| Policy compliance | read-only → staging → human gate ✓ |

## Follow-up

- `bb7x` (P2, T4): rotate `GH_TOKEN` to a fine-grained PAT with `Workflows:write` — **user action required** (only the user can create the PAT).
- Deferred (intentionally): `7d2.6` (Autonomy L0–L5, defer until intake loop ops-stable), `7d2.7` (MCP ecosystem wiring, token-bloat risk), `ar7.7` (GitHub rename, user action).
- Optional: wire `propose_playbook_evolution.py` into a periodic trigger (session-end / post-epic) so proposals accrue automatically for the human gate.
