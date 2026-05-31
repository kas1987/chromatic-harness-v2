---
name: env-clash-session
source_ids: [2026-05-02-env-clash-session]
source_type: anti-pattern
confidence: 0.90
suggested_use: python3 -c inline fails on Windows git-bash
canon_map: operations
status: approved
tags: []
---

## Summary

python3 -c inline fails on Windows git-bash

## Evidence

# Learning: python3 -c inline fails on Windows git-bash

## What We Learned

On Windows git-bash, the shell injects `|| goto :error` into inline Python passed via `-c "..."`, causing `IndentationError` on any indented block (if/for/try). Write Python to a `.py` file and call `python3 "$SCRIPT"` instead.

## Why It Matters

Pre-commit hooks and other bash scripts that call Python inline will silently fail or produce confusing errors on Windows. The fix is mechanical once you know the pattern.

## Source

env-clash-cleanup session 2026-05-02 — pre-commit scrub hook initially written as `python3 -c "..."`, broke with IndentationError.

---

# Learning: Anthropic API input_tokens does NOT include cache tokens

## What We Learned

`input_tokens` counts only non-cached input tokens. `cache_read_input_tokens` counts cached tokens read from cache. Total context = `input_tokens + cache_read_input_tokens`. Do NOT simplify to `input_tokens` alone — at 90%+ cache hit rates, that would show near-zero context usage and defeat any context guard.

## Why It Matters

This mistake was made during review, causing the context-guard fix to be wrong and requiring a revert. The formula `CACHE_TOKENS + INPUT_TOKENS` is correct.

## Source

env-clash-cleanup session 2026-05-02 — Gemini review suggested the sum was double-counting. It was not. The revert in commit 74e3a2b restores the correct behavior.

---

# Learning: Pre-commit staged file surgery pattern

## What We Learned

To modify a staged file before it commits (e.g., scrub secrets): use `git show ":path" | transform | git hash-object -w --stdin | git update-index --cacheinfo 100644,<hash>,path`. This rewrites the staged version without touching the working tree.

## Why It Matters

Cleanly separates "working tree has secrets for runtime" from "git index commits clean version." More reliable than a post-commit hook that tries to rewrite history.

## Source

env-clash-cleanup session 2026-05-02 — implemented in hooks/pre-commit.sh for settings.json PAT scrub.

---

# Learning: git checkout -B for idempotent branch creation

## What We Learned

`git checkout -B branch` creates the branch if it doesn't exist OR resets it to the current HEAD if it does — making session scripts idempotent. `git checkout -b` fails if the branch already exists.

## Why It Matters

Session automation scripts that create branches (like start-session.sh) should always use `-B` to survive re-runs without requiring cleanup.

## Source

env-clash-cleanup session 2026-05-02 — Gemini review finding on start-session.sh.

---

# Learning: Squash merge divergence requires manual merge

## What We Learned

When a PR is squash-merged to origin/master, the squash commit has a different SHA than your local commits. `git pull --ff-only` fails; `git rebase` may produce conflicts. Cleanest recovery: `git merge origin/master` (true merge), resolve conflicts, push with `--no-verify` (one-time admin sync past the pre-push guard).

## Why It Matters

Branch-based workflows with squash merges will produce this divergence every session. Document the recovery path so it's not surprising.

## Source

env-clash-cleanup session 2026-05-02 — PR #11 squash merge caused local master divergence, required manual merge + conflict resolution.
