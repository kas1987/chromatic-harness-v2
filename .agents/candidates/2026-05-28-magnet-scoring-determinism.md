---
name: 2026-05-28-magnet-scoring-determinism
source_ids: [2026-05-28-magnet-scoring-determinism]
source_type: learning
confidence: 0.90
suggested_use: Deterministic Magnet Scoring Beats Opaque Metrics
canon_map: general
status: pending
tags: []
---

## Summary

Deterministic Magnet Scoring Beats Opaque Metrics

## Evidence

# Learning: Deterministic Magnet Scoring Beats Opaque Metrics

## What We Learned

Using **explicit scoring rules** in magnets (confidence magnet: test_coverage 40%, lint 15%, type_checking 20%, code_quality 15%, review +10% bonus) proved far more useful than black-box ML scoring.

Why:
- **Explainability**: When confidence drops from 0.82 to 0.71, you can point to "test_pass_rate fell below 75%"
- **Debuggability**: Can tweak weights without retraining
- **Auditability**: Non-technical stakeholders (QA leads, product) can understand why a gate blocked
- **Predictability**: Same input always produces same score

## Why It Matters

In agent safety systems, explainability is non-negotiable. Automating decisions that affect deployment requires humans to audit the logic. Opaque scoring will fail that audit.

## What We'd Do Differently

Early versions of confidence magnet included ad-hoc anomaly bonuses that made scoring unpredictable. By Phase 4, we locked down the weights and never touched them again—that constraint proved right.

## Next: Weighted Portfolio Approach

For multi-objective scoring (cost efficiency, confidence, execution speed), consider a weighted portfolio approach: each magnet emits a (score, weight) pair, then synthesis does `weighted_avg = sum(score * weight) / sum(weight)`.

## Source

ConfidenceMagnet (02_RUNTIME/magnets/confidence-magnet.ts): 5 explicit scoring rules that passed all 7 magnet tests + 6 integration tests without modification.
