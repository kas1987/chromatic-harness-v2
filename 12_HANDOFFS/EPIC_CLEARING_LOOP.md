# Epic-Clearing Loop — State Tracker

> ✅ **COMPLETE (2026-06-01) — BOTH EPICS CLEARED.**
> ju0o (Collision Control, 8/8) + m52x (Runtime Governance, 10/10) closed.
> Terminal sequence done: `queue_self_review.py --apply` (no stale items),
> retro `docs/retros/2026-06-01-collision-control-epic.md`, learnings → bd.

Autonomous loop: ship every remaining epic child until both epics are cleared.
Resumable across turns.

## Protocol (per iteration)
1. `bd ready` → highest-priority unclaimed epic child → `bd update <id> --claim`.
2. `git worktree add -b <branch> ../<dir> origin/session/chromatic-harness-v2-initial`.
3. Build (salvage source if exists, else from scratch) + tests + register suite in `tests/run-all-e2e.py`.
4. `ruff check` + targeted `pytest` green → commit → push → PR.
5. Watch CI → merge (squash, delete branch) → flip eval boxes + `bd close` + `gh issue close` → `git worktree remove`.
6. Repeat until no `m52x.*` / `ju0o.*` open.
7. Terminal: close both epics, `queue_self_review.py --apply`, `/post-mortem`.

## Work-list — Collision Control (ju0o) — ✅ ALL SHIPPED
- [x] ju0o.1 — Lease MVP — PR #97
- [x] ju0o.2 — Mutation manifest enforcement — PR #101
- [x] ju0o.3 — Queue double-claim protection — PR #102
- [x] ju0o.4 — File-scope collision detection — PR #104
- [x] ju0o.5 — Stale lease recovery manager — PR #104
- [x] ju0o.6 — Agent heartbeat & renewal — PR #110
- [x] ju0o.7 — Deadlock detection — PR #110
- [x] ju0o.8 — Autonomous collision incidents — PR #110

## Work-list — Runtime Governance (m52x) — ✅ ALL SHIPPED
- [x] m52x.1–.10 incl m52x.7 (#85) + m52x.9 (#87) — epic closed.

## Done this loop
- ju0o.1 lease MVP — PR #97
- ju0o.2 mutation manifest enforcement — PR #101
- ju0o.3 queue double-claim protection — PR #102
- ju0o.4 + ju0o.5 — PR #104 (reconciled from concurrent commit 9840329, dropped duplicate)
- ju0o.6 + ju0o.7 + ju0o.8 — PR #110
- m52x runtime governance epic — closed (incl concurrent #85/#87)
- ju0o + m52x epics CLOSED → terminal sequence complete.
