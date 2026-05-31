# Token Governance Closed Loop

- Timestamp: 2026-05-31T20:10:35.953643+00:00
- Status: RED
- Pass: 3
- Warn: 0
- Fail: 1

## Checks

- PASS session_context_report: no warnings
- PASS audit_mcp_context: within threshold
- PASS validate_workflow_token_governance: workflow token governance OK
- FAIL daily_harness_audit_strict: status=red

## Refresh Chain

- OK quota_proxy_read
- OK portfolio_token_telemetry
- OK portfolio_token_forecast
- OK controller
- OK token_economy_exporter

## Suggestions

- token-gov-daily-audit-remediation: Remediate strict daily audit findings affecting token governance

## Queue Actions

- token-gov-daily-audit-remediation: skipped_existing
