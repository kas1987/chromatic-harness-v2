# OpenTelemetry Mapping

This document maps `harness_event.schema.json` fields to future OpenTelemetry attributes.

| Harness Field | OpenTelemetry Attribute |
|---|---|
| `event_id` | `event.id` |
| `task_id` | `chromatic.task.id` |
| `agent` | `chromatic.agent.name` |
| `model` | `gen_ai.request.model` |
| `event_type` | `chromatic.event.type` |
| `confidence_score` | `chromatic.confidence.score` |
| `risk_level` | `chromatic.risk.level` |
| `tools_used` | `chromatic.tools.used` |
| `files_touched` | `chromatic.files.touched` |
| `result` | `chromatic.result` |
| `duration_ms` | span duration |

## Span naming convention

```text
chromatic.<event_type>.<agent>
```

Examples:

- `chromatic.dispatch.orchestrator`
- `chromatic.execute.builder`
- `chromatic.validate.auditor`
