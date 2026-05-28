# API Routing Policy

> **Sonnet + Kimi governance:** see `docs/governance/MODEL_ROUTING_RULES.md` and `docs/governance/CONFIDENCE_GATE.md` for model-specific routing and confidence scoring. Governed by `docs/pdr/PDR-GOV-SONNET-KIMI-001.md`.

## Canonical Rule

No agent, repo script, workflow, or UI component should call external LLM APIs directly.
All calls must go through `ChromaticRouter.route()`.

## Provider Priority Ladder

| Rank | Provider Class | Use When | Avoid When |
|---:|---|---|---|
| 1 | Local: Ollama / LM Studio | private, cheap, repetitive, classification, simple drafting | high reasoning or long context needed |
| 2 | Broker: Featherless / OpenRouter | model experimentation, cheap cloud routing, fallback diversity | sensitive data or strict compliance tasks |
| 3 | Frontier: OpenAI / Anthropic / Google | high reasoning, code review, long synthesis, tool orchestration | low-value batch work |
| 4 | OpenHuman Sidecar | personal memory, integration context, background user/workflow context | primary routing, destructive actions, unreviewed OAuth/tool actions |

## Confidence Gate

| Score | Band | Allowed Behavior |
|---:|---|---|
| 90-100 | Very High | execute normally within scope |
| 75-89 | High | execute and log |
| 60-74 | Medium | execute only if reversible and low risk |
| 40-59 | Low | plan only; no external calls with sensitive data |
| 0-39 | Blocked | halt and escalate |

### Hard Rule
If confidence < 60, do not call OpenHuman, cloud providers, or tools with sensitive data.

## Privacy Classes

| Class | Description | Allowed Providers |
|---|---|---|
| P0 | public docs, public code, generic prompts | any approved provider |
| P1 | repo plans, non-secret project state | local, frontier, approved broker |
| P2 | personal context, private repo strategy, financial/legal docs | local or explicitly approved frontier only |
| P3 | API keys, tokens, credentials, private auth material | no LLM route; use secret manager only |
| P4 | legal, medical, compliance, irreversible business decisions | human gate + approved provider only |

## OpenHuman Boundary

- OpenHuman may receive P0-P2 only when explicitly enabled by route policy.
- OpenHuman must never receive P3 secrets.
- OpenHuman is **disabled by default**.
- OpenHuman is **read-only by default** when enabled.
