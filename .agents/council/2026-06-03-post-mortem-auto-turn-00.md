# Post-Mortem Council Report - Auto Turn Closeout

- generated_at_utc: 20260603T013140Z
- auto_turn_index: 0
- auto_turn_threshold: 5
- artifact_kind: post_mortem
- invoked_by: claude_code

## Outcome
- budget_decision: spawn
- epic_policy_allow_create: False
- epic_policy_confidence: 0.0
- epic_policy_reason: bd live query failed — blocking to prevent duplicate creation
- harvest_mode: session_end
- auto_start_ok: False

## Artifacts
- closeout_telemetry_latest: .agents/handoffs/closeout_telemetry_latest.json
- closeout_telemetry_history: .agents/handoffs/closeout_telemetry_20260603T013140Z.json

## Notes
- Generated automatically because auto-turn threshold was reached.
- Run harvest/session compaction and review governance recommendations next cycle.
