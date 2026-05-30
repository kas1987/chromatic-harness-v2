---
name: auto-turn-threshold-calibration
confidence: 0.82
status: candidate
category: governance
tags: auto-turn, rpi, checkpoint, policy, telemetry
---

# Auto-Turn Threshold Calibration

- generated_at_utc: 2026-05-30T11:00:55Z
- window_days: 14
- input_path: C:\Users\kas41\chromatic-harness-v2\.agents\handoffs\auto_turn_observations.jsonl
- rows_total: 5
- rows_triggered: 0

## Recommended Trigger Policy
- required_signal_hits: 2
- turn_threshold: 5
- loc_delta_total.min: 200
- policy_event_count.min: 100
- open_tasks.min: 2
- changed_files.min: 6

## Convergence Notes
- This report is generated from observed closeout behavior to calibrate checkpoint timing.
- Promote this file into the wiki to keep RPI threshold governance synchronized across rigs.
