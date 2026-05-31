---
name: integration-testing
source_ids: [2026-05-30-integration-testing-patterns]
source_type: pattern
confidence: 0.90
suggested_use: Module-Level Side Effects Require Env Isolation Before Import
canon_map: general
status: pending
tags: []
---

## Summary

Module-Level Side Effects Require Env Isolation Before Import

## Evidence

# Learning: Module-Level Side Effects Require Env Isolation Before Import

## What We Learned

When a module runs DB setup, file I/O, or environ reads at import time, importing it
without isolating the environment first produces corrupted or entangled state across tests.
Set up a tmpdir and patch `os.environ` *before* the first `import` of the module under test.

## Why It Matters

In this session, `CHROMATIC_DB_PATH` had to be set before `import api.db as db_module` to
prevent the test DB from landing in the repo root. Missing this causes all tests to share
the same DB state, making them order-dependent.

## Source

Integration test iteration for chromatic-harness-v2-bpq.4 (Agent Lead handoff integration).

---

# Learning: File-Based Event Stores Need Per-Run Isolation

## What We Learned

Append-only file stores accumulate data across test runs if the file path is stable.
Exact-count assertions (`assert len(replayed) == 7`) fail on reruns because prior run
events are still in the file. Use a unique tmpdir root per session or unique IDs per test.

## Why It Matters

`test_event_stream_visibility_for_frontend` initially asserted `len(replayed) == 7` and
failed with `21 == 7` on the second run because 3 prior runs had appended to the same file.
Fix: generate `mission_id = f"CHR-HANDOFF-{uuid.uuid4().hex[:8]}"` per test.

## Source

Integration test iteration for chromatic-harness-v2-bpq.4.

---

# Learning: Inspect Raw Output Before Writing Assertions

## What We Learned

When writing integration tests against complex return types, accessing an assumed attribute
path (e.g., `output.mission_id`) before inspecting the actual object shape wastes 3+ iteration
cycles. Print/log the raw value first, then write assertions from observed structure.

## Why It Matters

In this session, `AgentLeadOutput` stores the mission_id inside
`final_report["synthesis"]["mission_id"]`, not as a top-level attribute. This caused
4+ test iterations that could have been 1.

## Source

Integration test iteration for chromatic-harness-v2-bpq.4.
