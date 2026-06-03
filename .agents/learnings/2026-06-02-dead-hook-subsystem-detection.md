---
id: learning-2026-06-02-dead-hook-subsystem-detection
type: learning
date: 2026-06-02
category: devops
confidence: high
maturity: confirmed
---

# Learning: Use git config core.hooksPath to Find the Live Hooks Dir

## What We Learned

When a repo has multiple candidate hooks directories (e.g. `.git/hooks/`, `git_hooks/`, `hooks/+ci_local/`), `git config core.hooksPath` reveals which one Git ACTUALLY runs. Any other directory is ignored by Git regardless of its contents.

During `8lri.5`, we found an installer (`scripts/install_hooks.ps1`) with a "never clobber managed dir" guard that refused to write over a git-tracked target. Since `core.hooksPath` pointed at `git_hooks/` (a tracked directory), the installer's guard triggered on every run — meaning the installer had never successfully written its hooks. Its entire `hooks/+ci_local/` wiring was dead code. Retiring it changed zero live behavior.

## Why It Matters

Dead hook subsystems can look active (scripts exist, installer exists) while contributing nothing. Assuming a hooks directory is live without checking `core.hooksPath` leads to either: (a) wasted audit effort trying to understand non-running code, or (b) wrong assumptions about what safety checks are enforced.

## How to Apply

When auditing or debugging hooks behavior:
1. Run `git config core.hooksPath` — this is the ONLY active hooks dir
2. Check `git config --list | grep hook` for any hook-related overrides
3. Any hooks installer that guards against overwriting a managed dir pointed at by `core.hooksPath` is self-defeating — its output path is always pre-occupied
