# Magnets Spec

## Purpose

Magnets collect deterministic evidence around workflow inflection points and provide feedback, confidence deltas, risk deltas, and recommendations to the Agent Lead.

## Principles

1. Magnets observe; agents act.
2. Magnets produce structured events.
3. Magnets must be cheap enough to run frequently.
4. Magnets must be deterministic where possible.
5. Magnet findings must be replayable.

## Event Flow

```text
Inflection Point
→ Magnet Event
→ Magnet Report
→ Agent Lead Synthesis
→ Bead / PDR / Action
```
