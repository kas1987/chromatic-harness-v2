# Two-Log Audit

Zylos-style dual logging for harness workflows: **execution** (deterministic, never sampled) and **observability traces** (diagnostic, OTel GenAI stub).

## Logs

| Log | Path | Purpose |
|-----|------|---------|
| Execution | `07_LOGS_AND_AUDIT/execution/execution.jsonl` | Recovery, idempotency, side-effect receipts |
| Trace stub | `07_LOGS_AND_AUDIT/traces/traces.jsonl` | OTel-like spans (`gen_ai.*` attributes) without requiring OTLP |
| Decision | `07_LOGS_AND_AUDIT/decisions/decision_log.jsonl` | Confidence gates, bands, actions |
| Workflow (existing) | `docs/workflows/WORKFLOW_RUN_LOG.jsonl` (local; seed: `WORKFLOW_RUN_LOG.seed.jsonl`) | Human/agent-facing GO / activity history |

Activity events from `log_activity()` set `event_type` (e.g. `session.boot`, `phase.complete`, `git.failed`) and map to execution rows as `activity.<event_type>`.

## Wiring

Every `append_run_log()` call mirrors one row into all three audit logs via `02_RUNTIME/audit/two_log.py`.

```python
from audit.two_log import TwoLogAudit

audit = TwoLogAudit(repo_root)
audit.record_workflow_run({"mode": "GO", "bead_id": "...", "decision": "execute", ...})
```

## Execution entry fields

- `ts`, `mission_id`, `task_id`, `agent_role`, `event_type`
- `idempotency_key`, `input_hash`, `output_hash`
- `tool_name`, `tool_args_hash`, `side_effect_receipt`
- `prompt_version`, `model_version`, `workflow_decision`

## Trace stub

JSONL rows with `trace_id`, `span_id`, `name`, `kind`, `status`, `attributes` including:

- `gen_ai.operation.name`, `gen_ai.request.model`
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `workflow.mode`, `workflow.decision`, `harness.confidence_score`

Full OTLP export is deferred; this stub is the Silver-layer normalization target.

## Validate

```bash
python -m pytest tests/test_two_log_audit.py -q
python scripts/workflow_go.py "GO AUDIT"   # appends mirrored audit rows
```
