# LLM Governance Intelligence

Generated: 2026-05-30T07:53:40.041786+00:00
Event count: 4288

## Canonical Coverage

- timestamp: 100% (4286/4288)
- task_id: 79% (3394/4288)
- provider: 61% (2629/4288)
- model: 61% (2630/4288)
- task_type: 100% (4286/4288)
- execution_status: 61% (2614/4288)
- confidence_score: 51% (2205/4288)
- cost_usd: 0% (0/4288)
- latency_ms: 33% (1399/4288)

## Top Providers

- unknown: events=3330, success=1146, fail=497, unknown=1687
- mock: events=605, success=0, fail=0, unknown=605
- native_claude: events=302, success=0, fail=300, unknown=2
- gemini: events=20, success=20, fail=0, unknown=0
- openai: events=13, success=0, fail=4, unknown=9
- anthropic: events=5, success=0, fail=5, unknown=0
- openrouter: events=3, success=0, fail=2, unknown=1
- ollama: events=3, success=0, fail=3, unknown=0
- prism-orchestrator: events=3, success=0, fail=3, unknown=0
- google: events=3, success=0, fail=3, unknown=0

## Recommendations

- Improve telemetry: confidence_score coverage is 51%. Standardize this field in run-log schema.
- Critical telemetry gap: cost_usd coverage is 0%. Add mandatory logging in adapter + workflow emitters.
- Improve telemetry: latency_ms coverage is 33%. Standardize this field in run-log schema.
