---
name: session-closeout
source_ids: [2026-05-21-session-closeout-hook-cleanup]
source_type: principle
confidence: 0.90
suggested_use: MCP Server `--help` is a "Does It Start" Test
canon_map: knowledge
status: pending
tags: []
---

## Summary

MCP Server `--help` is a "Does It Start" Test

## Evidence

# Learning: MCP Server `--help` is a "Does It Start" Test

## What We Learned

MCP servers built with TypeScript (`@modelcontextprotocol/sdk`) ignore `--help`. When you run `node dist/index.js --help`, the server starts, prints its startup banner to stdout, and exits 0. The flag is a no-op. A test asserting `returncode == 0` is actually testing "does the entry point load without crashing" — which is still a valid and useful L3 smoke test, but the intent must be documented clearly.

## Why It Matters

Misleading test names erode trust in the test suite. A `test_node_entry_point_runs` test that looks like it tests `--help` handling, but doesn't, leads maintainers to add a second `test_help_flag` later, creating duplication. Naming and commenting must reflect actual behavior.

## Fix Applied

Added an inline comment clarifying the `--help` is ignored, and tightened the assertion to also check `stdout or stderr` is non-empty — catching silent crashes even if exit code stays 0.

## Source

Session 2026-05-21 — L3 smoke test for whisper-flow-mcp, caught during /vibe council.

---

# Learning: `@pytest.mark.skipif(not path.exists())` is Module-Load-Time Safe

## What We Learned

Python's `@pytest.mark.skipif(condition)` evaluates its condition at collection time (module import), not at test execution time. This makes `skipif(not DIST_INDEX.exists())` a reliable gate for "artifact not yet built" scenarios — pytest will skip the test during collection before any subprocess is launched.

## Why It Matters

This is the right pattern for L3 smoke tests that require a build artifact to exist. The alternative — a runtime `pytest.skip()` inside the test body — runs after collection and produces a different status (`S` vs. not collected). Use the decorator for structural preconditions, the runtime call for data-dependent skips.

## Source

Session 2026-05-21 — designing test_mcp_node_smoke.py.

---

# Learning: Bats Merge Conflict — Empty HEAD vs Feature Adds

## What We Learned

When merging a feature branch into master and both branches added content to the same region of a bats file, git produces a conflict even if master has no changes (the conflict is between the base state and the feature additions). In this case the resolution is always "take the feature content" — master's empty side was simply behind. Checking which side is non-empty before resolving saves time.

## Why It Matters

Bats conflicts where one side is empty are trivially resolved but can be confused with genuine two-side conflicts if the conflict markers aren't read carefully. The HEAD side being empty is a reliable signal to take the feature side unconditionally.

## Source

Session 2026-05-21 — resolving hook-audit/tests/hook-audit.bats during skills/ master merge.
