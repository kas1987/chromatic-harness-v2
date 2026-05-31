---
name: fixture-guard-mcp-layout
source_ids: [2026-05-21-fixture-guard-mcp-layout]
source_type: pattern
confidence: 0.90
suggested_use: Guard Tests Should Precede Dependent Tests
canon_map: general
status: approved
tags: []
---

## Summary

Guard Tests Should Precede Dependent Tests

## Evidence

# Learning: Guard Tests Should Precede Dependent Tests

## What We Learned

A test that depends on a fixture file (e.g., `cp "$FIXTURES_DIR/multi-event.json"`) will fail
with an opaque error if the fixture is absent. Adding a preceding `@test "fixture_X_exists"`
that does `[ -f "$FIXTURES_DIR/X" ]` surfaces the missing dependency at test-collection time
with a clear name, preventing silent false-greens when `run` absorbs the cp failure.

## Why It Matters

Silent false-greens from missing fixtures can mask regressions during refactors. The guard
pattern costs one test line and is self-documenting.

## Source

hook-audit.bats fixture_multi_event_json_exists guard added in 9cf7016.

---

# Learning: Env-Var Overrides Make Path-Resolving Tests Portable

## What We Learned

When a test resolves a path via a fixed relative chain (e.g., `Path(__file__).parent.parent.parent.parent / "dir"`),
the assumption breaks silently if the plugin or directory is relocated. Adding an
`MCP_DIR_OVERRIDE` env-var check before the default resolution documents the assumption
and makes the test portable across environments and CI configurations at zero cost.

## Why It Matters

One-line env-var override is the minimal, lowest-friction way to decouple a test's
directory assumptions from its physical layout. This pattern applies to any test
that resolves external tools, fixtures, or binaries via relative paths.

## Source

test_mcp_node_smoke.py MCP_DIR_OVERRIDE added in 893102d.
