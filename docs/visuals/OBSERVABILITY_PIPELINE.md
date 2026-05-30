# Observability Pipeline

```mermaid
flowchart TD
    Agent[Agent Run] --> Event[Harness Event JSON]
    Event --> JSONL[harness_events.jsonl]
    Event --> OTel[OpenTelemetry Mapping]

    OTel --> Collector[OpenTelemetry Collector]
    Collector --> Tempo[Tempo: Traces]
    Collector --> Prometheus[Prometheus: Metrics]
    Collector --> Loki[Loki: Logs]

    Tempo --> Grafana[Grafana Dashboard]
    Prometheus --> Grafana
    Loki --> Grafana

    JSONL --> MermaidGen[Mermaid Generator]
    MermaidGen --> Docs[docs/visuals]
```

## Minimum event fields

- `event_id`
- `timestamp`
- `task_id`
- `agent`
- `model`
- `event_type`
- `confidence_score`
- `risk_level`
- `tools_used`
- `files_touched`
- `result`
