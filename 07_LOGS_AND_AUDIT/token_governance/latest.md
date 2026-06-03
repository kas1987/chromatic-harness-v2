# Token Governance Closed Loop

- Timestamp: 2026-06-03T13:14:39.602540+00:00
- Status: RED
- Pass: 1
- Warn: 0
- Fail: 3

## Checks

- FAIL session_context_report: ERROR: mcps path not found: C:/Users/kas41/.cursor/projects/c-Users-kas41-chromatic-harness-v2/mcps
- FAIL audit_mcp_context: ERROR: mcps path not found: C:/Users/kas41/.cursor/projects/c-Users-kas41-chromatic-harness-v2/mcps
Set config/pre_session/settings.local.yaml mcp_descriptors_path
- PASS validate_workflow_token_governance: workflow token governance OK
- FAIL daily_harness_audit_strict: status=red

## Refresh Chain

- OK quota_proxy_read
- OK portfolio_token_telemetry
- OK portfolio_token_forecast
- OK controller
- OK token_economy_exporter

## Suggestions

- token-gov-context-budget: Reduce session context budget pressure and warnings
- token-gov-mcp-trim: Trim MCP token surface below profile warning threshold
- token-gov-daily-audit-remediation: Remediate strict daily audit findings affecting token governance

## Queue Actions

- token-gov-context-budget: queued
- token-gov-mcp-trim: queued
- token-gov-daily-audit-remediation: queued
