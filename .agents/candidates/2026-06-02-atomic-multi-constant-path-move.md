---
name: 2026-06-02-atomic-multi-constant-path-move
source_ids: [2026-06-02-atomic-multi-constant-path-move]
source_type: learning
confidence: 0.90
suggested_use: Update all hardcoded DEFAULT_* path constants in one atomic commit
canon_map: refactoring
status: approved
tags: [refactoring, paths, constants, atomicity]
---

## Summary

When a filesystem path appears as a `DEFAULT_*` constant in multiple files, updating them across separate commits silently splits the subsystem. Collision detection reads a different ledger than the writer. Land all constant updates — plus a cross-module equality assertion — in ONE commit.
