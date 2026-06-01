# Collision Avoidance & Claim Policy

> Bead `gl6t`. Stops the recurring failure modes: concurrent-agent branch/file
> collisions, shell contamination, and stale unclaimed beads that need manual
> cleanup. Enforced by `scripts/collision_guard.py` + `scripts/queue_self_review.py`.

## 1. One PR per issue, on a fresh branch

- Every issue/bead gets its **own feature branch** off the base, and its **own PR**.
- Never work directly on the shared `session/*` or `main` branch — `collision_guard`
  FAILs this (`named_branch`), because shared-branch work is what lets two agents
  stomp each other.
- Branch naming: `<issue-key>-<slug>` (e.g. `rg-081-go-mode`).

## 2. Claim before work — always

- Run `bd update <id> --claim` **before** writing any code for a bead.
- An `in_progress` bead **must** have an assignee. `queue_self_review` flags
  `unclaimed_active` for any in-progress bead with no assignee.
- `collision_guard --bead <id>` verifies the claim and warns if unclaimed.

## 3. When the target is already claimed → switch roles

If the bead/epic you intended to take is **already claimed or in progress by
another agent**, do **not** start a parallel implementation. Instead:

1. **Become a review agent** for that work — read its branch/PR, run its tests,
   leave review findings; or
2. **Pick an unclaimed bead** from `bd ready` that no one holds.

This is the single most important rule for avoiding duplicate work and the
merge collisions it causes.

## 4. Work in a dedicated worktree

- Use `git worktree add -b <branch> ../<dir> origin/<base>` so your checkout is
  **physically isolated** — another session's `git stash`, branch switch, or
  checkout cannot touch your files.
- `collision_guard` PASSes `worktree_isolation` inside a worktree and WARNs when
  you're on the main checkout while other worktrees are active.
- The orchestrator (`Agent` tool / `Workflow`) should set `isolation: "worktree"`
  for any agent that mutates files in parallel.

## 5. Commit shared-file edits immediately

- Shared files (`session_closeout.py`, `run-all-e2e.py`, `pyproject.toml`) are
  collision magnets. Edit → commit in the **same** turn.
- On any "my change vanished" surprise: **check the branch first**
  (`git branch --show-current`), then `git rev-parse HEAD` vs `origin/<branch>`,
  then `git show <branch>:<file>` — churn usually moved your checkout, it didn't
  delete your work (it may be in a `git stash`).

## 6. Shell contamination — avoid, don't persist

On Windows/Git-Bash long sessions the Bash tool intermittently returns stale
fragments and `cmd.exe` errors (`'~5' is not recognized`, `|| goto :error`).

- **Never** use inline `python -c "..."` for anything non-trivial — write a
  temporary `.py` file and run it, then delete it.
- Pass multi-line bead text via `bd update --body-file -` (stdin), ASCII-only.
- Re-verify suspicious output by writing to a file and reading it back, or use
  the dedicated Read/Grep tools instead of `cat`/`grep` in Bash.

## 7. Queue self-review replaces manual cleanup

`scripts/queue_self_review.py` runs read-only and proposes (never auto-applies):

| Finding | Meaning |
|---|---|
| `unclaimed_active` | in_progress bead with no assignee — claim or release |
| `ready_to_close` | all eval checkboxes `[x]` but still open — close candidate |
| `epic_ready_close` | epic open while every child is closed |
| `duplicate_ref` | two+ beads share one `external_ref` (seeding collision) |
| `stale_in_progress` | in_progress with no update in > N days |

Proposals land in `07_LOGS_AND_AUDIT/queue_self_review/latest.json`. A human
runs `--apply` to enact only the safe, reversible closes
(`ready_to_close` + `epic_ready_close`). This is the explicit gate; background
review never mutates the bead DB on its own.

## Enforcement points

- **Session start / pre-commit:** `collision_guard.py` (FAIL blocks).
- **Session closeout:** `queue_self_review.summarize()` + `collision_guard.summarize()`
  surface findings in the closeout report (fail-open).
- **Pre-push gate:** both test suites registered in `tests/run-all-e2e.py`.
