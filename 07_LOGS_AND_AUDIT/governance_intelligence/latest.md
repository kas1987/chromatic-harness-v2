# LLM Governance Intelligence

Generated: 2026-05-30T08:49:57.498016+00:00
Event count: 6318

## Canonical Coverage

- timestamp: 100% (6316/6318)
- task_id: 86% (5424/6318)
- provider: 74% (4654/6318)
- model: 74% (4655/6318)
- task_type: 100% (6316/6318)
- execution_status: 89% (5606/6318)
- confidence_score: 44% (2788/6318)
- cost_usd: 33% (2113/6318)
- latency_ms: 33% (2113/6318)

## Top Providers

- unknown: events=4594, success=1655, fail=502, unknown=2437
- workflow: events=672, success=224, fail=24, unknown=424
- mock: events=615, success=0, fail=0, unknown=615
- native_claude: events=306, success=0, fail=304, unknown=2
- gemini: events=98, success=98, fail=0, unknown=0
- openai: events=14, success=0, fail=4, unknown=10
- anthropic: events=5, success=0, fail=5, unknown=0
- openrouter: events=3, success=0, fail=2, unknown=1
- ollama: events=3, success=0, fail=3, unknown=0
- prism-orchestrator: events=3, success=0, fail=3, unknown=0

## Recommendations

- Improve telemetry: confidence_score coverage is 44%. Standardize this field in run-log schema.
- Improve telemetry: cost_usd coverage is 33%. Standardize this field in run-log schema.
- Improve telemetry: latency_ms coverage is 33%. Standardize this field in run-log schema.
