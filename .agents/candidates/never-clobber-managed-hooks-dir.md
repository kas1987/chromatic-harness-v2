---
name: never-clobber-managed-hooks-dir
source_ids: [2026-05-30-never-clobber-managed-hooks-dir]
source_type: anti-pattern
confidence: 0.85
suggested_use: A git-hook installer must resolve core.hooksPath and refuse managed dirs
canon_map: operations
status: pending
tags: []
---

## Summary

A git-hook installer must resolve core.hooksPath and refuse managed dirs

## Evidence

# A git-hook installer must resolve core.hooksPath and refuse managed dirs

## Observation

An installer that wrote into `$(git rev-parse --git-path hooks)` clobbered the active
`pre-commit` — because `core.hooksPath` was **redirected to `.beads/hooks`**, a
beads-managed, **git-tracked** directory. The overwrite shadowed the beads dispatcher.
(The repo's secrets-scrub turned out to be a separate Claude Code PreToolUse hook, so
no secret leaked this time — but the pattern is a real footgun.)

## Evidence

- `git config core.hooksPath` → `.beads/hooks` (not `.git/hooks`).
- `git ls-files --error-unmatch .beads/hooks/pre-commit` succeeded → tracked.
- The file carried `--- BEGIN BEADS INTEGRATION ---` markers (managed block).
- Recovery was clean: `git checkout -- .beads/hooks/pre-commit` (it was tracked).

## Recommendation

- Installers must resolve the **active** hooks dir: check `git config core.hooksPath`
  first, and only fall back to `git rev-parse --git-path hooks` if it is unset (the
  latter does not honor `core.hooksPath` on older git). Then **refuse** to overwrite
  when the target is git-tracked or contains a managed-block marker (e.g.
  `BEADS INTEGRATION`); advise manual wiring or append-after-marker instead.
- Distinguish git hooks from Claude Code hooks: a file named `pre-commit.sh` invoked as
  a *PreToolUse* handler is not the git `pre-commit`; don't conflate them.
- When clobbering tracked files, prefer recovery via `git checkout --` before anything else.
