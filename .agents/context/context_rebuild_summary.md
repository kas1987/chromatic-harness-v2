# Context Rebuild Summary

Generated: 2026-06-16T16:51:17.832387+00:00
Mode: soft
Risk Level: green

## Git

Branch: `chore/harness-cleanup-retention`

```text
M .agents/context/context_rebuild_summary.md
 M .agents/council/2026-06-03-post-mortem-auto-turn-00.md
 M .agents/handoffs/auto_turn_observations.jsonl
 M .agents/handoffs/closeout_telemetry_latest.json
 M .agents/handoffs/successor_prompt.md
 M .agents/handoffs/transfer_packet.json
 M .agents/harvest/latest.json
 M .beads/interactions.jsonl
 M .chromatic/last_known_good.json
 M .github/workflows/branch-governance-weekly.yml
 M .github/workflows/ci-governance-weekly.yml
 M .github/workflows/ci.yml
 M .vscode/tasks.json
 M 00_META/observability/reports/OBSERVABILITY_REPORT_2026-06-03.md
D  02_RUNTIME/api/10_RUNTIME/logs/agentops-events.jsonl
 M 02_RUNTIME/runtime-engines/roach-pi
 M 05_REPORTS/telemetry.jsonl
 M 07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl
 M 07_LOGS_AND_AUDIT/active_sessions.sqlite3
 M 07_LOGS_AND_AUDIT/budget/forecast_latest.json
 M 07_LOGS_AND_AUDIT/budget/ledger.jsonl
 M 07_LOGS_AND_AUDIT/budget/monthly.json
 M 07_LOGS_AND_AUDIT/command_matrix/latest.json
 M 07_LOGS_AND_AUDIT/control_plane/routing_policy_overlay.json
 M 07_LOGS_AND_AUDIT/drift/baseline.json
 M 07_LOGS_AND_AUDIT/drift/history.jsonl
 M 07_LOGS_AND_AUDIT/drift/latest.json
 M 07_LOGS_AND_AUDIT/governance_intelligence/canary_snapshot_latest.json
 M 07_LOGS_AND_AUDIT/harness_health/latest.json
 M 07_LOGS_AND_AUDIT/harness_health/latest.md
 M 07_LOGS_AND_AUDIT/issue_intake/latest.json
 M 07_LOGS_AND_AUDIT/operations/dr_inventory.json
 M 07_LOGS_AND_AUDIT/root_artifacts/latest_root_artifact_hygiene.json
 M 07_LOGS_AND_AUDIT/security/latest.json
 M 07_LOGS_AND_AUDIT/token_governance/history.jsonl
 M 07_LOGS_AND_AUDIT/token_governance/latest.json
 M 07_LOGS_AND_AUDIT/token_governance/latest.md
 M 07_LOGS_AND_AUDIT/unified_guard/latest.json
 M 12_HANDOFFS/PRE_SESSION_INVENTORY.md
 M config/pre_session/inventory.snapshot.json
 M docs/PRE_SESSION_AND_TOOLS.md
D  docs/workflows/WORKFLOW_RUN_LOG.jsonl
 M git_hooks/pre-commit
 M scripts/branch_governance_autonomy.py
 M scripts/log_retention.py
 M scripts/session_boot_automation.py
 M scripts/token_governance_closed_loop.py
 M scripts/workflow_self_heal_cycle.py
 M tests/test_log_retention.py
?? .agents/council/2026-06-04-post-mortem-auto-turn-00.md
?? .agents/council/2026-06-16-post-mortem-auto-turn-00.md
?? .agents/handoffs/closeout_telemetry_20260603T181345Z.json
?? .agents/handoffs/closeout_telemetry_20260603T181348Z.json
?? .agents/handoffs/closeout_telemetry_20260603T193610Z.json
?? .agents/handoffs/closeout_telemetry_20260603T193611Z.json
?? .agents/handoffs/closeout_telemetry_20260603T212453Z.json
?? .agents/handoffs/closeout_telemetry_20260603T212454Z.json
?? .agents/handoffs/closeout_telemetry_20260603T230104Z.json
?? .agents/handoffs/closeout_telemetry_20260603T230108Z.json
?? .agents/handoffs/closeout_telemetry_20260604T011058Z.json
?? .agents/handoffs/closeout_telemetry_20260604T011059Z.json
?? .agents/handoffs/closeout_telemetry_20260604T171332Z.json
?? .agents/handoffs/closeout_telemetry_20260604T171335Z.json
?? .agents/handoffs/closeout_telemetry_20260604T172322Z.json
?? .agents/handoffs/closeout_telemetry_20260604T172325Z.json
?? .agents/handoffs/closeout_telemetry_20260604T214451Z.json
?? .agents/handoffs/closeout_telemetry_20260604T215450Z.json
?? .agents/handoffs/closeout_telemetry_20260616T161535Z.json
?? .agents/handoffs/closeout_telemetry_20260616T161727Z.json
?? .agents/handoffs/closeout_telemetry_20260616T161728Z.json
?? .chromatic/latest_snapshot.json
?? .large-file-allowlist
?? 00_META/observability/reports/OBSERVABILITY_REPORT_2026-06-04.md
?? 00_META/observability/reports/OBSERVABILITY_REPORT_2026-06-16.md
?? 07_LOGS_AND_AUDIT/ci/
?? 07_LOGS_AND_AUDIT/drift/20260604T003734Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160117Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160204Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160409Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160503Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160626Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160650Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160811Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160816Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160903Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T160938Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161229Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161343Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161348Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161408Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161409Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161457Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161523Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161616Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161618Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161621Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161702Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161827Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161854Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T161954Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162129Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162203Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162427Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162457Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162556Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162733Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T162818Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163029Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163101Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163322Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163333Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163411Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163631Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163711Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163849Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T163933Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164012Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164233Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164308Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164529Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164605Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164632Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164635Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164740Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164835Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164839Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T164916Z.json
?? 07_LOGS_AND_AUDIT/drift/20260616T165030Z.json
?? 08_PDRS/SWOT_AUTONOMY/
?? scripts/large_file_gate.py
?? scripts/swot_autonomy_loop.py
?? tests/test_large_file_gate.py
```

## Handoff

Pointer exists: True
Handoff path: 12_HANDOFFS/sessions/CHR-HANDOFF-9720c3e6.md

## Beads

```text
bd unavailable or no ready output
```

## Next Action

Select one active bead and load only task-relevant docs.
