# Token Governance Closed Loop

- Timestamp: 2026-05-31T20:46:51.260121+00:00
- Status: RED
- Pass: 2
- Warn: 1
- Fail: 1

## Checks

- PASS session_context_report: no warnings
- WARN audit_mcp_context: Heavy MCP servers still present on disk: user-review-daemon
- PASS validate_workflow_token_governance: workflow token governance OK
- FAIL daily_harness_audit_strict: status=red

## Refresh Chain

- OK quota_proxy_read
- OK portfolio_token_telemetry
- OK portfolio_token_forecast
- OK controller
- OK token_economy_exporter

## Suggestions

- token-gov-mcp-trim: Trim MCP token surface below profile warning threshold
- token-gov-daily-audit-remediation: Remediate strict daily audit findings affecting token governance

## Queue Actions

- token-gov-mcp-trim: skipped_existing
- token-gov-daily-audit-remediation: skipped_existing
