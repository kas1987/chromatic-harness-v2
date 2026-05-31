---
name: bats-guard-test-before-consumer
type: anti-pattern
confidence: 0.90
source_learnings: [2026-05-21-bats-guard-test-before-consumer]
description: Learning: Add fixture-existence guard before bats consumer tests
tags: []
---

# Learning: Add fixture-existence guard before bats consumer tests

## What We Learned

When a bats test copies a fixture file with `cp "$FIXTURES_DIR/foo.json"`, add a `@test "fixture_foo_json_exists"` guard immediately before it. Without the guard, a missing fixture causes `cp` to fail silently — bats still runs the consumer test against whatever state was left (often empty), producing a false-green.

## Why It Matters

Silent false-greens are the worst kind of test failure: CI passes, the fixture dependency rots, and the bug is only discovered when the guard-less consumer test runs in an environment where the fixture was never created.

## Source

hook-audit epic fixture-guard-mcp-layout-2026-05-21, task-1. Pattern generalises to any bats test that copies or sources a fixture file.
