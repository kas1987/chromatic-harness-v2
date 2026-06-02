# Session Retrospective — Operating-Model Hardening (OMH)

**Date:** 2026-06-02
**Epics closed:** `chromatic-harness-v2-w1bf` (OMH) — 9/9 children
**PRs merged:** #208, #213, #216, #217, #218, #220, #222

## What shipped

OMH epic closed gaps in `docs/CHROMATIC_OPERATING_MODEL.md` — mostly wiring/surfacing/closing systems that already existed.

- **w1bf.4 (#208)** — review-intake wired live end-to-end on a real PR (`--emit-beads` → real bead in `bd ready`; evidence-gated resolution comment posted back). Runbook `docs/pdr/review_intake/LIVE_WIRING.md`.
- **w1bf.5 (#213)** — `scripts/error_log_to_learning.py`: CI/harness failures → `bd remember`-ready learning candidates, staged read-only (never auto-promoted).
- **session_start fix (#216)** — Windows `bd prime` no-op fixed via shared `_bd_argv()`.
- **w1bf.6 (#217)** — `docs/WIKI_CONVERGENCE_CADENCE.md` + cross-repo promotion dedup in `promote_to_wiki.py` (content-hash ledger, `--repo-id`/`--cadence` provenance).
- **w1bf.8 (#218)** — `docs/governance/SKILL_PROFILES.md`: 12 per-task hot-swap profiles + token-debt audit.
- **w1bf.9 (#220)** — `docs/playbooks/INDEX.md` coverage audit (8 operating levels) + `PROMOTE_PLAYBOOK.md` (filled the only hole).
- **w1bf.7 (#222)** — `scripts/root_hygiene_gate.py` root-allowlist gate + removed `INTEGRATION_TEST.ts`.

(w1bf.1/.2/.3 — collision awareness, router enforcement, loop guards — landed before this session.)

## Learnings

### 1. Windows `bd.CMD` subprocess no-op
`subprocess.run(["bd", ...])` raises `FileNotFoundError` on Windows: `bd` is a `bd.CMD` npm shim and `CreateProcess` only auto-appends `.exe` (it ignores PATHEXT for a bare spawn). A `shutil.which("bd")` *gate* passes (it resolves `bd.CMD`) yet the bare-name exec still fails — and a `try/except FileNotFoundError` then silently degrades, so the call never runs and falsely reports "bd not on PATH". `gh`/`git` are safe (real `.exe`). Found via the OMH-4 live run; the same pattern lurked in `session_start.py:361`.
**Action:** Execute the `shutil.which`-resolved absolute path (or `cmd /c` fallback). Captured in bd memory `windows-bd-subprocess-pathext`.

### 2. The pre-push e2e gate only runs registered suites
`tests/run-all-e2e.py` `SUITES` is the real gate. Several shipped subsystems (session_start, wiki promotion) had passing tests that were **never in SUITES** — so they didn't actually gate pushes. Registered session_start, wiki, and root-hygiene suites this session.
**Action:** When adding a core-subsystem test, register it in `SUITES` in the same PR, or it's decorative.

### 3. "Wire it live" surfaces bugs fixtures can't
The Windows no-op (Learning 1) was invisible to unit tests because they monkeypatch `subprocess.run`. It only appeared when running `--emit-beads` against a real PR. Faithful live-wiring tasks are worth doing literally, not simulating.
**Action:** For "wire live" beads, run the real command against a real target; self-reference the task's own PR when a real artifact is needed (truthful, low-noise).

### 4. Concurrent autonomous runner ⇒ work in worktrees
A long-running next-task supervisor churned branches mid-session (switched my checkout, merged #209–#214, left staged WIP). No work was lost (everything was on remote feature branches), but it's a real hazard.
**Action:** Per task, isolate in a `git worktree` off the latest base; stage only your own files; remove the worktree after push. Expect `run-all-e2e.py` `SUITES` merge conflicts when both sides append — resolve by keeping *both* suite entries.

## KPI snapshot
| KPI | Value |
|-----|-------|
| OMH children landed | 9/9 |
| PRs merged | 7 |
| Latent Windows bugs fixed | 2 (dispatch, session_start) |
| Previously-ungated suites registered | 3 |

## Follow-up
- No open OMH beads. In-progress beads belong to the concurrent v3 runner (`8lri.6`, agent beads), not this work.
- Next ready work (`bd ready`): v3 epics — `8lri` (repo reorg), `w0wk` (schema registry), `u8uj` (typed runtime core).
