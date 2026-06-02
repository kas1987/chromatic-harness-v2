---
name: 2026-06-02-dead-hook-subsystem-detection
source_ids: [2026-06-02-dead-hook-subsystem-detection]
source_type: learning
confidence: 0.90
suggested_use: Use git config core.hooksPath to find the live hooks directory
canon_map: devops
status: approved
tags: [git, hooks, devops, dead-code]
---

## Summary

`git config core.hooksPath` reveals the ONLY hooks directory Git actually runs. An installer that guards against overwriting a git-tracked target pointed at by `core.hooksPath` is self-defeating — its hooks output path is always occupied, so it never writes, making all its hooks dead code. Retiring such an installer changes zero live behavior.
