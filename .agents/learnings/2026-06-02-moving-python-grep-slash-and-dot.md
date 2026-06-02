---
id: learning-2026-06-02-moving-python-grep-slash-and-dot
type: learning
date: 2026-06-02
category: refactoring
confidence: high
maturity: confirmed
---

# Learning: Grep Both Slash-Path and Dotted-Import Forms When Moving Python Dirs

## What We Learned

Moving an importable Python module/directory requires grepping for TWO reference forms, not one:

1. **Slash-path**: `old/dir/`, `old/dir/file.py` — caught by most string searches
2. **Dotted-import**: `old.dir`, `import old.sub`, `importlib.import_module("old.sub")` — missed by path-only grep

During the `8lri.2` legacy-dir retirement, `dashboards/exporter/` was moved but `importlib.import_module("dashboards.exporter.token_economy_exporter")` in `token_governance_closed_loop.py` was missed, causing CI to go red on the test job (not caught by pre-push, which only runs the run-all-e2e SUITES list).

## Additional Nuance

Numeric-prefix dirs (e.g. `09_DEPLOYMENT`) are NOT importable as dotted module names — Python identifiers cannot start with a digit. Keep them on `sys.path` as a path ENTRY so the inner package name still resolves:

```python
sys.path.insert(0, str(REPO / "09_DEPLOYMENT"))
import dashboards.exporter.token_economy_exporter  # resolves via sys.path
```

## Why It Matters

The pre-push gate only runs suites in `run-all-e2e.py SUITES`; broader CI catches dotted-import misses. A green pre-push does not guarantee a green CI test job after a module move.

## How to Apply

Before committing a Python module/dir move:
1. `grep -r "old/dir" .` for slash forms
2. `grep -r "old\.dir\|import old\|import_module.*old" .` for dotted forms
3. Run the full test suite locally (`pytest tests/`) not just the e2e suite
