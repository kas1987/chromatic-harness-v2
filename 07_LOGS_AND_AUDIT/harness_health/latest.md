# Harness Health Snapshot

- generated_at_utc: 2026-06-03T01:32:27Z
- overall_status: red
- readiness_score: 0/100

## Check Results

| Check | Status | Message |
|---|---|---|
| unified_guard_ok | fail | ok=False |
| token_governance_green | fail | status=red |
| pre_session_fresh | fail | age_min=None |
| unified_guard_fresh | pass | age_min=0.1 |
| handoff_present | fail | handoff_present=False |
| mcp_budget | pass | over_warn_threshold=False |
| coverage_provider_model | warn | provider=0.7366 model=0.7368 llm_events=0 |
| coverage_task_exec | warn | task_id=0.8585 execution_status=0.8873 llm_events=0 |
| coverage_confidence_cost_latency | fail | confidence=0.4413 cost=0.3344 latency=0.3344 |
| agent_log_fresh_and_populated | pass | age_min=73.18 lines=1 |
| codegraph_sample_size | pass | paired_count=1 |
| budget_forecast_present | pass | forecast artifact loaded |
| weekly_budget_optimization | pass | state=at_or_above_target target_pct=75.0 gap_target_usd=0.0 need_per_day_usd=0.0 |
| forecast_accuracy_present | pass | accuracy artifact loaded |
| forecast_accuracy_weekly | pass | status=green week_mape_pct=0.0 |
| budget_channels_present | pass | channels=6 vscode_week=0.0 cursor_week=0.0 |
| forecast_channel_trend_present | pass | trend artifact loaded |
| forecast_channel_trend_status | pass | status=green |

## Coverage

- provider: 0.7366
- model: 0.7368
- task_id: 0.8585
- execution_status: 0.8873
- confidence_score: 0.4413
- cost_usd: 0.3344
- latency_ms: 0.3344

