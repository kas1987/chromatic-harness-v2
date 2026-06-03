# Session Retrospective — Worker-spawn git-worktree isolation

**Date:** 2026-06-02
**PRs merged:** [#238](https://github.com/kas1987/chromatic-harness-v2/pull/238), [#239](https://github.com/kas1987/chromatic-harness-v2/pull/239)
**Epics closed:** none (targeted hardening of two dispatch entrypoints)

## What shipped

- **#239 — `claude_delegate_gate.py` worktree isolation.** `_spawn_claude()` ran the
  `claude -p` worker via `run_safe(cmd, cwd=REPO)` in the *shared* checkout; if the
  worker created/switched branches it moved the main HEAD and corrupted concurrent
  interactive git work. Now it creates an isolated `git worktree` on a fresh
  `delegate/<id>` branch, runs the worker with `cwd=<worktree>`, tears it down in a
  `finally`, and **refuses to spawn** (rather than falling back to the shared
  checkout) if the worktree can't be created. Mirrors the `task_runner.py` pattern
  from #238 (`_create_worktree`/`_remove_worktree`/`_run(cwd=...)`).
- **#238 — review-feedback hardening** (Copilot, 3 comments, all addressed + resolved):
  1. `_create_worktree()` now `mkdir(parents=True, exist_ok=True)` on `.worktrees/`
     before `git worktree add` (which does not create parents).
  2. `.worktrees/` added to the **committed** `.gitignore`.
  3. Non-autonomous permission hint now keys off `_RESULT_MARKER not in out` (raw
     worker output) instead of a substring of the synthesized summary.
- Tests mirror `test_task_runner.py`'s worktree suite (runs-in-worktree + cleanup,
  refuse-on-failure, cleanup-on-failure, path sanitization, mkdir-parent,
  marker-based hint). New file registered in `tests/run-all-e2e.py` so the guard
  gates pushes.

## Learnings

### 1. `git worktree add` does not create missing parent directories
Creating `.worktrees/auto-x` assumes `.worktrees/` exists. On a fresh clone (with
`isolate_worktree` defaulting on) the parent is absent, so every dispatch would fail
to create the worktree and the runner would refuse all work.
**Action:** Always `mkdir(parents=True, exist_ok=True)` the worktree root before
`git worktree add`. Captured in bd: `git-worktree-add-does-not-create-missing-parent`.

### 2. `.worktrees/` was ignored only by the *local* global-exclude
`git check-ignore .worktrees/foo` returned true locally — but the source was
`~/.gitignore_global`, not the repo's committed `.gitignore`. On CI and other clones
the per-worker worktrees showed up as untracked and dirtied git state. The original
#238 comment even claimed it was "gitignored" — true only on my machine.
**Action:** When ignoring a new runtime dir, verify it's in the *committed*
`.gitignore` (`git show HEAD:.gitignore`), not just `git check-ignore`. Captured in
bd: `worktrees-was-ignored-only-via-the-local-gitignore`.

### 3. Don't gate behavior on self-synthesized message wording
The permission hint fired when `"RUNNER_RESULT" in result.summary` — which only worked
because `_parse_worker_result()` happens to synthesize "no RUNNER_RESULT line from
worker". Fragile: reword the summary and the behavior silently breaks.
**Action:** Gate on the actual signal (`_RESULT_MARKER not in out`, the worker's raw
output). Captured in bd: `review-hint-robustness-gate-behavioral-hints-on-the`.

### 4. Mid-session branch churn is an active hazard — recover without touching the live checkout
The working branch switched under me repeatedly: a commit meant for one branch landed
on a *sibling open PR's* branch (#236), and edited files reverted to original between
tool calls. Recovery: cherry-pick the commit onto a fresh branch off `origin/main`
inside an isolated `git worktree` (never switching the live checkout), push it as its
own PR, then un-pollute the sibling branch with
`git push origin <parent>:<branch> --force-with-lease=<branch>:<sha>`.
**Action:** Commit immediately after editing; verify the branch before/after every
commit/push; prefer explicit-ref pushes and isolated worktrees over `git checkout`.
Captured in bd: `branch-churn-recovery-pattern-when-mid-session-branch` (reinforces
existing `automode-midsession-branch-hazard`).

## Process notes

- The reported CI failure ("Concurrency Suite py3.11") was **transient** — that run
  died ~1s after `setup-python`, before pytest, while a parallel py3.11 run passed.
  Re-pushing produced a fully green run. Worth distinguishing "no test output, died in
  setup" from a real assertion failure before chasing a fix.
- Review feedback on a fix should be propagated to any **mirrored** code in flight:
  the same mkdir/gitignore gaps existed in #239 and were fixed in the same session.

## Follow-up

- Both PRs are **merged**; nothing outstanding for this work.
- The comment reference `docs/retros/2026-06-02-omh-pr233-gate-fix.md` cited in the
  worktree-isolation code does not exist as a file (the related retro is
  `2026-06-02-omh-operating-model-hardening.md`). Low priority: fix the dangling
  reference or add the named doc on a future docs pass.
- Next work: `bd ready`.
