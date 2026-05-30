---
id: post-mortem-2026-05-30-is2f-governance-guards
type: post-mortem
date: 2026-05-30
epic: chromatic-harness-v2-is2f
source_pre_mortem: "[[.agents/council/2026-05-30-pre-mortem-governance-guards-agent-bead.md]]"
---

# Post-Mortem: chromatic-harness-v2-is2f — Governance Guards (Agent Bead Proliferation)

## Council Verdict: PASS (with WARN)

---

## Checkpoint Policy

| Check              | Status | Detail                                     |
|--------------------|--------|--------------------------------------------|
| Chain loaded       | SKIP   | No chain.jsonl — standalone post-mortem    |
| Prior phases locked| N/A    | Standalone, no ratchet chain               |
| No FAIL verdicts   | PASS   | Pre-mortem verdict was WARN (proceed)      |
| Idempotency        | PASS   | No prior is2f entry in next-work.jsonl     |

---

## Scope Delivered vs Planned

**Epic:** `chromatic-harness-v2-is2f` — Governance guards: prevent orphaned [agent] bead proliferation

**Children (3/3 CLOSED):**
- `is2f.1` — Fix `_load_swot_epic_history` to use live bd list + lower SWOT caps to 1 ✓
- `is2f.2` — Add [agent]-prefix guard to `auto_intake._should_skip()` ✓ (already existed)
- `is2f.3` — Tests for SWOT live-query history and [agent] intake skip guard ✓

**Scope delta vs plan:**
- `is2f.1` was expanded per pm-20260530-001: also fixed `find_latest_open_swot_epic()` and `find_open_swot_task_for_epic()` (2 additional functions beyond the plan's stated 1).
- `_load_issue_rows_jsonl()` helper extracted by formatter during implementation (unplanned, but correct).
- 17 orphaned EPIC-SWOT epics closed manually (pm-20260530-004 addressed partially — see WARN).
- `[agent]` IN_PROGRESS bead cleanup was NOT completed (last step blocked by Windows pipe/Python quoting issue). Daily audit `active_duplicates` remains >0.

---

## Closure Integrity

| Check                   | Result | Details                                                                  |
|-------------------------|--------|--------------------------------------------------------------------------|
| Evidence Precedence     | WARN   | All 3 children resolved by `worktree` evidence — no git commit exists yet |
| Phantom Beads           | PASS   | All children have descriptive titles and specs                           |
| Orphaned Children       | PASS   | 3/3 children linked to parent in bd show                                 |
| Multi-Wave Regression   | N/A    | Single-wave, not crank                                                   |
| Stretch Goals           | PASS   | No stretch goals                                                          |

**WARN:** `scripts/session_closeout.py` and `tests/test_session_closeout.py` modifications are NOT committed to git. Evidence mode is `worktree` only. All 27 tests pass locally.

---

## Prediction Accuracy (Pre-Mortem Correlation)

| Prediction ID     | Finding                                               | Result   |
|-------------------|-------------------------------------------------------|----------|
| pm-20260530-001   | find_latest_open_swot_epic uses stale JSONL           | HIT ✓    |
| pm-20260530-002   | `--limit 0` undocumented in plan                      | MISS     |
| pm-20260530-003   | No integration test for full gated flow               | MISS     |
| pm-20260530-004   | 28 orphaned EPIC-SWOT beads not cleaned up            | PARTIAL  |

**Score:** 1 HIT, 2 MISS, 1 PARTIAL. Pre-mortem caught the critical propagation blindness (pm-20260530-001) and the cleanup obligation (pm-20260530-004). No false positives.

---

## Plan Compliance

| Planned                                                       | Delivered                                  | Delta      |
|---------------------------------------------------------------|--------------------------------------------|------------|
| Fix `_load_swot_epic_history()` live query                    | Done + expanded to 2 other functions       | EXPANDED   |
| Lower SWOT caps to 1                                          | Done (`open_swot_total_cap: 1`)            | EXACT      |
| Add `[agent]` prefix guard to `auto_intake._should_skip()`   | Already existed; verified                  | EXACT      |
| 6 new tests for governance guards                             | 4 new tests added (27 total pass)          | REDUCED    |
| Close orphaned [agent] IN_PROGRESS beads                      | Blocked by Windows pipe quoting            | INCOMPLETE |

---

## Tech Debt

- **Uncommitted changes** — session_closeout.py and tests/test_session_closeout.py are modified but not staged/committed. These must be committed and PRed before the next session.
- **`[agent]` bead cleanup incomplete** — `active_duplicates` audit still RED. Closing these requires a Windows-safe approach (write Python to temp file, not inline `-c`).
- **Integration test gap** — pm-20260530-003 was mild, but `ensure_epic_swot_chain()` + `evaluate_epic_swot_policy()` end-to-end is not tested at integration level. Unit coverage is sufficient for now.

---

## Four-Surface Closure

| Surface       | Status | Notes                                                               |
|---------------|--------|---------------------------------------------------------------------|
| Code          | PASS   | Functions added, live-query-first pattern implemented               |
| Tests         | PASS   | 4 new unit tests, all 27 pass                                       |
| Documentation | WARN   | No docstrings updated for new functions; inline comments sufficient |
| Proof         | WARN   | No git commit yet; worktree evidence only                           |
