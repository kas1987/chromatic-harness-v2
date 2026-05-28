# Confidence Gate — Sonnet + Kimi Governance

> **See also:** `docs/routing/API_ROUTING_POLICY.md` — the canonical confidence gate thresholds that apply to all providers, not just Sonnet/Kimi.

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
  "decision": "execute | plan_only | halt"
}
```

Append this block to `07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl` as part of every run record.

## Thresholds

| Confidence | Band | Allowed Action |
|---:|---|---|
| 90–100 | Very High | Execute scoped task |
| 75–89 | High | Execute with logging |
| 60–74 | Medium | Only reversible low-risk changes |
| 40–59 | Low | Plan only — no mutations |
| 0–39 | Blocked | Halt and escalate |

These thresholds align exactly with `API_ROUTING_POLICY.md §Confidence Gate`.

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
