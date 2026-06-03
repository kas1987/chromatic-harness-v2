---
id: learning-2026-06-02-atomic-multi-constant-path-move
type: learning
date: 2026-06-02
category: refactoring
confidence: high
maturity: confirmed
---

# Learning: Update All Hardcoded Path Constants in One Atomic Commit

## What We Learned

When a filesystem path is hardcoded as a `DEFAULT_*` constant in multiple files, updating them across separate commits silently splits the subsystem across two paths. During `8lri.6`, `state/leases/active_leases.jsonl` was hardcoded independently in:

- `scripts/lease_manager.py` — `DEFAULT_LEDGER`
- `scripts/claim_guard.py` — its own `DEFAULT_LEDGER`
- `scripts/collision_check.py` — CLI `--ledger` default

Moving only `lease_manager.py` meant collision detection was reading a different ledger than the writer — a silent split-brain that would produce false "no collision" results until the second commit landed.

## Why It Matters

Split-brain path state is worse than a broken import: it fails silently. Tests that only exercise one side of the subsystem stay green while the other side operates on a stale/empty file.

## How to Apply

Before moving a path:
1. `grep -r "state/leases"` (or the old path) across ALL scripts, not just the obvious one
2. Assert at test time that `lease_manager.DEFAULT_LEDGER == claim_guard.DEFAULT_LEDGER` (or equivalent cross-module equality)
3. Land all constant updates in ONE commit — never partially migrate a shared state path
