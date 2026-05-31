---
name: beads-intake
type: pattern
confidence: 0.90
source_learnings: [2026-05-28-beads-unified-intake]
description: Learning: Structured Action Intake via Beads Unifies Multi-Source Findings
tags: []
---

# Learning: Structured Action Intake via Beads Unifies Multi-Source Findings

## What We Learned

Converting all execution outcomes (closed tasks, anomalies, learnings, evidence) into a single **Bead** structure (type: action|alert|learning|score) eliminated the "findings format chaos" problem.

Before: Magnets emit anomalies, gates emit verdicts, execution emit results—three different schemas with no standard interface. Leads to:
- Custom parsing per source
- Humans context-switching between UI panels for findings
- Duplicate/contradictory alerts

After: Everything becomes a Bead. Dashboard shows one queue, humans work one interface. BeadsBridge normalizes all sources:
- Magnet anomalies → alert beads (with risk_delta mapping to priority)
- Closed tasks → action beads
- Learnings → learning beads
- Confidence evidence → score beads

## Why It Matters

Consistency reduces cognitive load. When everything is a Bead, the human reviewing the queue knows the schema, sorting, and filtering rules apply uniformly.

## Real Impact

Phase 6 dashboard integration was trivial because the backend already shipped beads as a unified model. If gates/magnets/execution each had separate queue endpoints, Phase 6 would have required 3x more mapping code.

## Lesson for Future Systems

Any multi-source finding system (linters, formatters, custom checks, external APIs) should normalize to a single findings structure before surfacing to UI.

## Source

BeadsBridge (02_RUNTIME/beads-bridge.ts): Converts ExecutionResult → [Bead] across 4 types with unified priority/severity mapping.
