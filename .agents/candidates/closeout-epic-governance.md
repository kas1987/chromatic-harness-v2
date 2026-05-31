---
name: closeout-epic-governance
source_ids: [2026-05-30-closeout-epic-governance]
source_type: anti-pattern
confidence: 0.90
suggested_use: Governed EPIC Reuse Beats EPIC Proliferation
canon_map: operations
status: approved
tags: []
---

## Summary

Governed EPIC Reuse Beats EPIC Proliferation

## Evidence

# Learning: Governed EPIC Reuse Beats EPIC Proliferation

## What We Learned

Adding confidence-scored policy gates is not sufficient by itself. Governance controls must include deterministic reuse of an existing open EPIC and open task to preserve telemetry continuity and prevent issue churn.

## Why It Matters

This keeps backlog growth intentional, improves historical comparability, and prevents automation from creating low-signal duplicate EPICs.

## Source

Post-mortem on closeout governance and EPIC policy hardening (2026-05-30).

---

# Learning: Canonical Coverage Parsing Must Be Shape-Tolerant

**ID**: L2
**Category**: testing
**Confidence**: high

## What We Learned

Governance telemetry may emit canonical coverage fields as either scalar numbers or nested dicts. Consumers must normalize both forms before scoring to avoid runtime conversion failures.

## Why It Matters

Shape-tolerant parsing prevents brittle policy engines and reduces false negative gates caused by schema drift.

## Source

closeout policy evaluation and test hardening for session closeout.
