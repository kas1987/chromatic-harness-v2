# LLM Governance Intelligence

Generated: 2026-05-30T06:40:10.817378+00:00
Event count: 2641

## Canonical Coverage

- timestamp: 100% (2639/2641)
- task_id: 66% (1747/2641)
- provider: 37% (984/2641)
- model: 25% (660/2641)
- task_type: 100% (2639/2641)
- execution_status: 72% (1901/2641)
- confidence_score: 66% (1731/2641)
- cost_usd: 0% (0/2641)
- latency_ms: 53% (1392/2641)

## Top Providers

- unknown: events=1708, success=460, fail=495, unknown=753
- mock: events=603, success=0, fail=0, unknown=603
- native_claude: events=299, success=0, fail=297, unknown=2
- openai: events=13, success=0, fail=4, unknown=9
- anthropic: events=5, success=0, fail=5, unknown=0
- openrouter: events=3, success=0, fail=2, unknown=1
- ollama: events=3, success=0, fail=3, unknown=0
- prism-orchestrator: events=3, success=0, fail=3, unknown=0
- google: events=3, success=0, fail=3, unknown=0
- lmstudio: events=1, success=0, fail=0, unknown=1

## Recommendations

- Improve telemetry: provider coverage is 37%. Standardize this field in run-log schema.
- Critical telemetry gap: model coverage is 25%. Add mandatory logging in adapter + workflow emitters.
- Critical telemetry gap: cost_usd coverage is 0%. Add mandatory logging in adapter + workflow emitters.
- Improve telemetry: latency_ms coverage is 53%. Standardize this field in run-log schema.
