---
name: 2026-06-02-moving-python-grep-slash-and-dot
source_ids: [2026-06-02-moving-python-grep-slash-and-dot]
source_type: learning
confidence: 0.90
suggested_use: Grep both slash-path and dotted-import forms when moving Python dirs
canon_map: refactoring
status: approved
tags: [python, refactoring, ci, imports]
---

## Summary

Moving an importable Python module/dir requires grepping BOTH slash-path (`old/dir/`) AND dotted-import (`old.dir`, `importlib.import_module("old.sub")`) forms. Missing dotted forms causes CI red on the test job even when pre-push passes. Numeric-prefix dirs (e.g. `09_DEPLOYMENT`) are not importable as dotted names — add them to `sys.path` as a path entry instead.
