# Learning Tier Calibration Review

Weekly process for reviewing learning tier health and triggering E1 threshold
rebalancing after two completed cycles.

---

## Cadence

**Frequency:** Weekly (every 7 days from first run date).
**Owner:** session operator (TwistKS or delegated agent).
**Trigger:** Run `python scripts/calibrate_e1_threshold.py` — it detects cycle
boundaries automatically from `.agents/audit/calibration-cycles/`.

---

## Weekly Checklist

Run in order each week:

1. **Regenerate tier report**
   ```
   python scripts/compute_learning_tiers.py
   ```
   Produces `07_LOGS_AND_AUDIT/learning_tiers/latest.json` and `latest.md`.

2. **Review pyramid health**
   - What fraction of learnings are still at E0?
   - Are any learnings trending toward E1 (score ≥ 0.28, uses ≥ 1)?
   - Are any E1+ learnings regressing?

3. **Check E0 candidates near E1 boundary**
   ```
   python scripts/calibrate_e1_threshold.py --dry-run
   ```
   Reports: how many learnings are within 0.05 score units of the E1 min_score.

4. **Review usage log coverage**
   - File: `.agents/metrics/learning_usage.jsonl`
   - Are applied_success / applied_failure events being emitted in workflows?
   - Zero events for a week = usage logging is broken or no learnings were applied.

5. **Apply rebalance (cycle 2+ only)**
   ```
   python scripts/calibrate_e1_threshold.py
   ```
   If two cycles are complete, the script applies the rebalance rubric and writes
   an audit artifact. See [Rebalance Rubric](#rebalance-rubric) below.

6. **Commit calibration artifacts**
   Stage and commit:
   - `07_LOGS_AND_AUDIT/learning_tiers/latest.*`
   - `.agents/audit/calibration-cycles/<YYYY-MM-DD>.json` (if rebalance ran)
   - `config/learning_tier_policy.json` (if threshold changed)

---

## Metrics Required for Calibration

| Metric | Source | Description |
|--------|--------|-------------|
| `e0_total` | `latest.json pyramid.E0` | Learnings stuck at Candidate tier |
| `e1_total` | `latest.json pyramid.E1` | Learnings at Emerging tier |
| `near_e1_count` | computed | E0 learnings with score within 0.05 of E1 min_score |
| `graduation_rate` | computed | `e1_total / (e0_total + e1_total)` |
| `avg_score_e0` | computed from `items` | Mean score of all E0 learnings |
| `usage_events_7d` | `.agents/metrics/learning_usage.jsonl` | Events in last 7 days |
| `e1_min_score` | `config/learning_tier_policy.json` | Current E1 score threshold |
| `cycles_completed` | `.agents/audit/calibration-cycles/` | Count of prior calibration runs |

---

## Rebalance Rubric

Applied automatically when `cycles_completed >= 2`.

**Decision tree:**

```
graduation_rate < 0.05 AND near_e1_count >= 3
  → LOWER e1 min_score by 0.02 (floor: 0.28)
  → log: "too many learnings stranded near E1 boundary"

graduation_rate > 0.30 AND e1_min_score < 0.40
  → RAISE e1 min_score by 0.02 (ceiling: 0.45)
  → log: "E1 threshold too permissive, learnings graduating too easily"

else
  → NO CHANGE (threshold is calibrated)
  → log: "graduation_rate=<x>, within acceptable band"
```

Each rebalance writes an audit artifact to `.agents/audit/calibration-cycles/`
with: `cycle_number`, `date`, `before_threshold`, `after_threshold`,
`graduation_rate`, `near_e1_count`, `decision`, and `rationale`.

---

## Cycle Boundary Definition

A calibration cycle is one completed weekly run of this process. The cycle
counter is the number of JSON files in `.agents/audit/calibration-cycles/`.
The rebalance trigger fires when `cycle_count >= 2` **and** the current run's
date is at least 7 days after the most recent prior run.

---

## Audit Trail

All rebalance decisions are append-only in `.agents/audit/calibration-cycles/`.
Never delete or edit historical artifacts. Each file is named
`YYYY-MM-DD-calibration.json` (one per weekly run).
