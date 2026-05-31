---
name: whisper-call-parallel-mcp-l2-tests
source_ids: [2026-05-02-whisper-call-parallel-mcp-l2-tests]
source_type: anti-pattern
confidence: 0.90
suggested_use: unittest.mock patch captures the module reference at patch time
canon_map: operations
status: pending
tags: []
---

## Summary

unittest.mock patch captures the module reference at patch time

## Evidence

# Learning: unittest.mock patch captures the module reference at patch time

**ID**: L1

## What We Learned

`patch("subprocess.Popen", side_effect=lambda cmd, **kw: __import__("subprocess").Popen(...))` causes infinite recursion on Python 3.11 Windows because `__import__("subprocess")` returns the already-patched module — the lambda calls the mock, which calls the lambda, which calls the mock. The fix is to capture `original_popen = subprocess.Popen` *before* entering the `patch()` context manager, then reference `original_popen` inside the lambda.

## Why It Matters

This pattern appears in the plan for L2 integration tests. The plan's `__import__` trick was wrong and would crash with a stack overflow. The correct pattern (capture before patch) is the standard idiom for "real passthrough with modified args."

## Source

whisper-call L2 integration tests — `test_mcp_call_real_subprocess_*` tests, 2026-05-02

---

# Learning: Windows thread startup adds ~60ms to ThreadPoolExecutor wall time

**ID**: L2

## What We Learned

On Windows 11, `ThreadPoolExecutor` thread creation adds approximately 50–70ms of overhead per new thread pool (not per submit). A parallelism timing test with 50ms sleeps and a 90ms threshold reliably fails (~109ms actual) because the pool creation time consumes the entire margin. Solution: use 100ms simulated delays and a 175ms threshold, giving >25ms of margin while still proving parallelism (sequential baseline would be ≥200ms).

## Why It Matters

Parallelism timing tests that pass on Linux/Mac can fail systematically on Windows. Budget ≥75ms of margin on Windows timer-based assertions.

## Source

whisper-call ThreadPoolExecutor timing test, 2026-05-02 — first attempt with 50ms/90ms threshold failed at 109ms

---

# Learning: Fake MCP subprocess server is a better L2 fixture than Popen mocks

**ID**: L3

## What We Learned

Replacing `subprocess.Popen` mocks with a real Python fake server (reads fixture JSON from argv[1], speaks JSON-RPC over stdio) exercises the full IPC pathway: JSON serialization, line buffering, subprocess lifecycle, and `terminate()`. The fake server adds ~0.2s to a 4-test suite — negligible cost for meaningfully higher signal.

## Why It Matters

`Popen` mocks validate that `_mcp_call` calls the right methods in the right order, but they don't catch: malformed JSON in stdout, wrong Content-Type in MCP response, or `terminate()` racing with stdout reads. The real subprocess catches all of these.

## Source

whisper-call `tests/helpers/fake_mcp_server.py` + `tests/test_mcp_integration.py`, 2026-05-02
