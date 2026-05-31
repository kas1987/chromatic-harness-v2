---
name: governance-guards-is2f
source_ids: [2026-05-30-governance-guards-is2f]
source_type: principle
confidence: 0.90
suggested_use: Live-Query-First Pattern for Policy Guards
canon_map: knowledge
status: approved
tags: []
---

## Summary

Live-Query-First Pattern for Policy Guards

## Evidence

# Learning: Live-Query-First Pattern for Policy Guards

## What We Learned

Any policy function that reads bead state to make cap decisions (e.g., SWOT epic caps) must query `bd list` live first and fall back to JSONL only on failure. Reading stale `.beads/issues.jsonl` silently bypasses all caps because closed beads remain in the file with stale statuses.

## Why It Matters

A single stale-JSONL reader can make a "block duplicate creation" gate completely ineffective. The `_fetch_swot_rows_live() → fallback` pattern prevents this for the SWOT subsystem.

## Source

chromatic-harness-v2-is2f — pm-20260530-001 prediction confirmed.

---

# Learning: Windows Inline Python Pipe Quoting Failure

## What We Learned

On Windows CMD/PowerShell, `bd list --json | python -c "import sys; [... || ...]"` fails with `IndentationError: unexpected indent` because CMD interprets `||` inside the Python string as a shell OR operator. The workaround is to write Python to a temp file and run it as a script (`python temp.py`), or use a subprocess within Python to call `bd`.

## Why It Matters

This pattern is a recurring trap — any inline Python with `||` will silently fail on Windows. Use `python script.py` or `python -c "..."` with no `||` operators in the inline code.

## Source

chromatic-harness-v2-is2f cleanup step — blocked by Windows pipe issue.

---

# Learning: Test Isolation Requires Mocking Live bd Queries

## What We Learned

When tests call functions that issue live `bd list` queries, those tests must mock the live query helper (`_fetch_swot_rows_live`) to prevent real bead state from overriding test fixtures. Without the mock, tests pass locally when no matching beads exist and fail when the real backlog has open beads.

## Why It Matters

Tests with external CLI side-effects are environment-dependent and non-deterministic. Always patch live-query helpers with `unittest.mock.patch.object` when unit-testing policy evaluation functions.

## Source

chromatic-harness-v2-is2f.3 — test_evaluate_epic_swot_policy and test_find_latest_open_swot_epic both failed until mocked.
