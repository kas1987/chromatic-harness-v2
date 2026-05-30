# Confidence Gate — Sonnet + Kimi Governance

> **See also:** `docs/routing/API_ROUTING_POLICY.md` — provider routing.  
> **Runtime GO:** [docs/workflows/GO_MODES.md](../workflows/GO_MODES.md) — self-heal band and `workflow_go.py`.

## Purpose

Prevent Sonnet or Kimi from mutating project state before scope, evidence, risk, and reversibility are clear.

## Required Score Block

Before any mutation, the active model must produce and log this JSON:

```json
{
  "confidence_score": 0,
  "risk_level": "low | medium | high | critical",
  "scope_clarity": 0,
  "evidence_quality": 0,
  "reversibility": "yes | partial | no",
  "decision": "execute | plan_only | halt | self_heal"
}
```

Append this block to `07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl` as part of every run record.

## Canonical bands (GO + CMP)

Aligned with `02_RUNTIME/orchestrator/confidence_engine.py` and `02_RUNTIME/workflows/self_heal.py`:

| Score | Workflow decision | Agent action |
|------:|-------------------|--------------|
| 0–49 | `halt` | Stop; escalate |
| 50–69 | `plan_only` + **`self_heal`** | Auto task graph + intake enqueue; run `workflow_self_heal_cycle.py` or `/go` |
| 70–74 | `plan_only` | Human review or manual `GO DEEP` — no auto mutation |
| 75–89 | `execute` (reversible) | Scoped work with logging |
| 90–100 | `execute` | Scoped task |

`mutation_allowed()` requires `execute` and score ≥ 75.

## Stop Rule

Stop immediately and report when:

- confidence drops below the band required for the current action
- `risk_level` is `critical` and no human approval has been given
- `reversibility` is `no` and confidence < 90
- the same file is read more than twice without measurable progress
- task expands outside declared `scope` in the mission packet
- tests fail twice in a row

## Who Enforces This

The Chromatic Orchestrator (`02_RUNTIME/`) validates confidence scores before promoting any Kimi-produced artifact to the main branch or dispatching any Sonnet mutation task. Gate failures are logged to `07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl` with `result: "gate_blocked"`.
