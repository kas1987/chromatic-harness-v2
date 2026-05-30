# Model Routing Rules: Sonnet + Kimi

> **See also:** `docs/routing/API_ROUTING_POLICY.md` — the full provider priority ladder (Ollama → Featherless → Frontier → OpenHuman). This document adds Kimi-specific routing on top of that policy.
> **See also:** `docs/routing/PROVIDER_MATRIX.md` — capability matrix for all registered providers.

## Role Assignment

See also:

- `docs/governance/LLM_GOVERNANCE_INTELLIGENCE_LOOP.md`
- `docs/governance/OFFICIAL_LLM_RESOURCE_WATCHLIST.md`

| Role | Model | Primary Function |
|---|---|---|
| Architect / Reviewer | Sonnet | Planning, synthesis, critique, documentation, risk review, governance checks |
| Builder / Scout | Kimi | Repo scanning, implementation drafts, refactors, long-context file digestion, repeated worker tasks |

No model may act as an unbounded autonomous agent. Every dispatch requires a mission packet (see `AGENT_MISSION_PACKET_TEMPLATE.md`).

## Default Routing

| Task Type | Preferred Model | Reason |
|---|---|---|
| Architecture decisions | Sonnet | Strong synthesis and design reasoning |
| PDR writing | Sonnet | Strong structure and documentation |
| Governance review | Sonnet | Better risk and contradiction detection |
| Repo scanning | Kimi | Strong long-context file digestion |
| Implementation draft | Kimi | Capable builder / refactor model |
| Refactor pass | Kimi | Good scoped worker |
| Final audit before merge | Sonnet | Strong review and critique |
| Ambiguity resolution | Sonnet | Preferred for decisions with unclear scope |

## Required Workflow Patterns

### Standard Pattern

```text
Kimi builds → Sonnet reviews → Human/Orchestrator approves or reroutes
```

### High-Risk Pattern

```text
Sonnet plans → Kimi implements → Sonnet audits → Human approves
```

Use the high-risk pattern when `risk_level` is `high` or `critical` per the confidence gate.

## Anti-Patterns — Do Not Do These

- **Do not let Kimi self-approve** high-impact changes.
- **Do not let Sonnet re-plan endlessly** without producing a queued bead or task.
- **Do not dispatch either model** without a filled mission packet.
- **Do not let either model** touch files outside its declared `scope`.
- **Do not route Kimi** for ambiguity resolution — escalate to Sonnet or human.
- **Do not route Sonnet** for cheap repeated worker tasks that fit within Kimi's budget.

## Confidence Gate Integration

Both models must score confidence before any mutation. See `CONFIDENCE_GATE.md` for thresholds and stop conditions.

## Logging

Every Sonnet or Kimi run must append a record to `07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl`. See the schema there.
