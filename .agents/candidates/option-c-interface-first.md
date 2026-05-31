---
name: option-c-interface-first
source_ids: [2026-05-28-option-c-interface-first]
source_type: pattern
confidence: 0.90
suggested_use: Interface-First Design for Multi-Runtime Orchestration
canon_map: general
status: pending
tags: []
---

## Summary

Interface-First Design for Multi-Runtime Orchestration

## Evidence

# Learning: Interface-First Design for Multi-Runtime Orchestration

## What We Learned

Defining the RuntimeAdapter contract **before** implementing any phase prevented coupling across 6+ phases. The abstraction enabled:

- Independent testing of magnets, gates, beads without runtime specifics
- WebSocket (Phase 6.5) to integrate in 1 day (not 1 week) because boundaries were clean
- roach-pi adapter + 3 placeholder adapters (LangGraph, OpenHands, custom) all follow the same contract
- Zero rework when adding agent trust profiles—the interface pre-mapped safety concerns

## Why It Matters

Real-world multi-agent systems often fail when runtime-specific code leaks into governance layers. This architecture proved the pattern: governance is **orthogonal** to execution mechanism.

- Changing gate logic doesn't touch adapter code
- Adding new magnets works for all runtimes simultaneously
- Safety validation (L0-L5) is runtime-agnostic

## Actionable Pattern

1. **Design the contract first** (via interfaces + JSON schema)
2. **Implement the most complex phase first** (Phase 2: Magnets) — if it fits the contract, all simpler phases will too
3. **Verify contract completeness** via multi-layer integration test (Phase E2E)
4. **Add runtimes last** — they are implementations, not architecture

## Source

Chromatic Harness v2 Option C: All 6 phases + Phase 6.5 shipped without refactoring the RuntimeAdapter interface.
