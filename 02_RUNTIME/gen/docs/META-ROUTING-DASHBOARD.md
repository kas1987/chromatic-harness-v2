# Gen meta-routing — operator queries

Examples for backends that ingest OTLP from Gen (`gen-orchestrator`). Metric names match [`gen/src/otel/meter.ts`](../src/otel/meter.ts). Span attributes match [`gen/src/otel/attributes.ts`](../src/otel/attributes.ts).

## Prometheus / Mimir-style

**Routing reconciliation rate** (how often clients report `activeLlm` vs suggestion):

```promql
sum(rate(gen_routing_reconciliation_total[5m])) by (result)
```

**Mismatch share** (of reported reconciliations):

```promql
sum(rate(gen_routing_reconciliation_total{result="mismatch"}[1h]))
/
sum(rate(gen_routing_reconciliation_total{result!="unknown"}[1h]))
```

**User-prompt normalizer bypasses:**

```promql
sum(rate(gen_user_prompt_bypass_total[5m])) by (reason)
```

**Session routing store pressure:**

```promql
gen_session_routing_store_entries
gen_session_routing_store_evictions_total
```

## Trace queries (Jaeger / Tempo)

- Filter spans: `gen.routing_reconciliation=mismatch`
- Filter spans: `gen.intent_tool_coherence=mismatch_soft`
- Filter spans: `gen.policy_layer=budget`

Parent linking: ensure hook HTTP clients send header **`traceparent`** (W3C); Gen uses it as the parent context for `hook.pretool`, `hook.posttool`, `hook.user-prompt`.

## SQLite (longer retention than traces)

On the Gen database file (`GEN` config / `config.databasePath`):

```sql
SELECT ts, hook_event, session_id, suggested_llm, actual_llm, routing_reconciliation, intent_tool_coherence
FROM routing_decisions
ORDER BY ts DESC
LIMIT 100;
```

```sql
SELECT prompt_intent, active_llm, suggested_llm, tool_used, succeeded, recorded_at
FROM task_outcomes
WHERE active_llm IS NOT NULL
ORDER BY recorded_at DESC
LIMIT 50;
```
