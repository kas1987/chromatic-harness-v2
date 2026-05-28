# PDR-API-ROUTING-OPENHUMAN.md

## 0. PDR Metadata

| Field | Value |
|---|---|
| PDR ID | PDR-API-ROUTING-OPENHUMAN |
| Title | Chromatic API Routing + OpenHuman Integration Gateway |
| Status | Draft for Implementation |
| Version | 0.1.0 |
| Owner | Chromatic Harness / Human Owner |
| Created | 2026-05-28 |
| Target Repo Path | `docs/pdr/PDR-API-ROUTING-OPENHUMAN.md` |
| Related Systems | Chromatic Harness, GO-mode, Model Routing, Confidence Gates, OpenHuman, Ollama, LM Studio, Featherless, OpenRouter, OpenAI, Anthropic, Google |
| Decision Type | Architecture / Integration / Governance |
| Implementation Priority | P1 |

---

## 1. Executive Decision

Chromatic Harness will implement a provider-neutral API routing layer that routes model, tool, and agent calls through one internal contract before reaching external providers or local runtimes.

OpenHuman will be integrated first as a routed sidecar endpoint, not as the primary router or orchestrator.

This prevents OpenHuman from becoming an uncontrolled second brain while still letting Chromatic Harness benefit from its memory tree, integrations, background context ingestion, local-first vault model, and agentic desktop/runtime capabilities.

### Decision

```text
Chromatic Router remains captain.
OpenHuman becomes a governed routed endpoint.
All calls pass through confidence, budget, privacy, and observability gates.
```

---

## 2. Problem Statement

The current Chromatic Harness stack needs a clean routing layer for deciding which model, provider, local runtime, or agent service should handle each request.

Without this PDR, the system risks:

- scattered provider calls
- hardcoded API keys
- duplicated routing logic
- runaway token/tool use
- unclear fallback behavior
- weak audit trails
- provider lock-in
- OpenHuman memory drift
- unsafe account/OAuth integration exposure
- multiple agents acting as if they are the main orchestrator

OpenHuman introduces extra value but also extra governance risk because it can combine memory, integrations, background sync, tool access, model routing, and managed OAuth flows.

---

## 3. Goals

### Primary Goals

1. Create one internal API routing contract for all model/provider calls.
2. Route across local, hosted, and agent-sidecar providers.
3. Integrate OpenHuman safely as a sidecar service.
4. Preserve Chromatic Harness governance as the source of authority.
5. Add confidence, cost, privacy, and risk gates before provider selection.
6. Add observability for every route decision.
7. Support fallback chains without manual reprompting.
8. Keep implementation simple enough to ship in one sprint.

### Non-Goals

This PDR does not attempt to:

- replace Chromatic Harness with OpenHuman
- blindly sync all Chromatic memory into OpenHuman
- expose all local files to OpenHuman by default
- create a production SaaS gateway immediately
- solve every OAuth integration on day one
- implement every provider SDK at once

---

## 4. Source Assumptions

OpenHuman is treated as an active beta dependency and must be isolated behind adapters.

Known OpenHuman characteristics from public project materials:

- local memory tree, Obsidian-style Markdown vault, workspace config, and local runtime state
- managed services by default for sign-in, model routing, web search proxying, and integrations/OAuth through Composio
- support for custom/local model, search, or Composio credentials
- integrations including Gmail, Notion, GitHub, Slack, Stripe, Calendar, Drive, Linear, Jira, and others
- memory canonicalization into Markdown chunks and SQLite-backed summary trees
- optional local AI via Ollama for supported workloads
- early beta status with expected rough edges

Because OpenHuman is beta, all integration points must be versioned, reversible, and protected by feature flags.

---

## 5. Architecture Decision

### Selected Architecture

```text
User / Agent / GO Command
        |
        v
Chromatic API Router
        |
        +-- Confidence Gate
        +-- Privacy Classifier
        +-- Cost Budget Gate
        +-- Tool/Provider Policy
        +-- Observability Logger
        |
        v
Provider Adapter Layer
        |
        +-- Local Adapter: Ollama
        +-- Local Adapter: LM Studio
        +-- Cloud Adapter: OpenAI
        +-- Cloud Adapter: Anthropic
        +-- Cloud Adapter: Google
        +-- Broker Adapter: OpenRouter
        +-- Broker Adapter: Featherless
        +-- Sidecar Adapter: OpenHuman
        |
        v
Response Normalizer
        |
        v
Chromatic Harness State / Queue / Logs
```

### Key Rule

No agent, repo script, workflow, or UI component should call external LLM APIs directly after this PDR is implemented.

All calls must go through the router.

---

## 6. Routing Policy

### Provider Priority Ladder

| Rank | Provider Class | Use When | Avoid When |
|---:|---|---|---|
| 1 | Local: Ollama / LM Studio | private, cheap, repetitive, classification, simple drafting | high reasoning or long context needed |
| 2 | Broker: Featherless / OpenRouter | model experimentation, cheap cloud routing, fallback diversity | sensitive data or strict compliance tasks |
| 3 | Frontier: OpenAI / Anthropic / Google | high reasoning, code review, long synthesis, tool orchestration | low-value batch work |
| 4 | OpenHuman Sidecar | personal memory, integration context, background user/workflow context | primary routing, destructive actions, unreviewed OAuth/tool actions |

### Task-to-Provider Defaults

| Task Type | Default Route | Backup Route | Notes |
|---|---|---|---|
| Simple classification | Ollama | LM Studio | cheap local first |
| Repo implementation | Codex / code model via router | Claude / GPT | must include file scope |
| Long planning | Claude / GPT | Gemini | high reasoning path |
| Current research | Web/search-capable model | OpenHuman only if connected context is needed | cite sources when external |
| Personal context lookup | OpenHuman sidecar | local vault search | no blind memory sync |
| Gmail/Calendar/Drive integration context | OpenHuman sidecar only if authorized | native connector/tools | OAuth risk gate required |
| Sensitive project docs | local model first | approved frontier model | no unknown broker route |
| Vision/multimodal | Gemini/GPT vision | OpenAI/Anthropic vision | provider capability based |
| Cheap swarm triage | local small model | Featherless/OpenRouter | hard budget cap |

---

## 7. Confidence Gate

Every route request must receive a confidence score before execution.

### Confidence Inputs

| Factor | Weight |
|---|---:|
| Objective clarity | 20% |
| Provider fit | 20% |
| Privacy risk clarity | 15% |
| Cost fit | 15% |
| Context sufficiency | 15% |
| Reversibility | 10% |
| Testability | 5% |

### Confidence Bands

| Score | Band | Allowed Behavior |
|---:|---|---|
| 90-100 | Very High | execute normally within scope |
| 75-89 | High | execute and log |
| 60-74 | Medium | execute only if reversible and low risk |
| 40-59 | Low | plan only; no external calls with sensitive data |
| 0-39 | Blocked | halt and escalate |

### Rule

```text
If confidence < 60, do not call OpenHuman, cloud providers, or tools with sensitive data.
```

---

## 8. Privacy Classes

| Class | Description | Allowed Providers |
|---|---|---|
| P0 Public | public docs, public code, generic prompts | any approved provider |
| P1 Internal | repo plans, non-secret project state | local, frontier, approved broker |
| P2 Sensitive | personal context, private repo strategy, financial/legal docs | local or explicitly approved frontier only |
| P3 Secret | API keys, tokens, credentials, private auth material | no LLM route; use secret manager only |
| P4 Regulated/High-Risk | legal, medical, compliance, irreversible business decisions | human gate + approved provider only |

### OpenHuman Boundary

OpenHuman may receive P0-P2 only when explicitly enabled by route policy.

OpenHuman must never receive P3 secrets.

---

## 9. OpenHuman Integration Model

### Phase 1: Sidecar Read-Only Context

OpenHuman is used only for contextual lookup and memory-assisted answers.

Allowed:

- health check
- memory search/query
- non-destructive integration summaries
- read-only contextual handoff

Forbidden:

- sending emails
- modifying calendars
- mutating GitHub
- deleting files
- writing to Chromatic source-of-truth memory
- acting as primary orchestrator

### Phase 2: Governed Tool Execution

OpenHuman may execute selected tools only through Chromatic-issued mission packets.

Requirements:

- task ID
- allowed tool list
- allowed account/integration list
- privacy class
- budget cap
- stop conditions
- full audit log

### Phase 3: Bidirectional Memory Bridge

Only after Phase 1 and Phase 2 pass review.

Memory bridge must be selective, not automatic.

Allowed bridge types:

- project summaries
- user-approved context capsules
- non-secret workflow state
- final decisions

Forbidden bridge types:

- API keys
- raw private inbox exports
- raw calendar dumps
- uncontrolled repo files
- sensitive personal records

---

## 10. Router Request Contract

All route requests use this shape.

```json
{
  "request_id": "uuid",
  "task_id": "string",
  "task_type": "classification | planning | coding | review | research | personal_context | integration_action",
  "objective": "string",
  "input": {
    "messages": [],
    "files": [],
    "metadata": {}
  },
  "constraints": {
    "privacy_class": "P0 | P1 | P2 | P3 | P4",
    "max_cost_usd": 0.25,
    "max_latency_ms": 30000,
    "max_tokens": 8000,
    "allow_cloud": true,
    "allow_broker": true,
    "allow_openhuman": false,
    "allow_tools": false
  },
  "confidence": {
    "score": 0,
    "band": "blocked",
    "reason": "string"
  },
  "preferred_provider": "auto | ollama | lmstudio | openai | anthropic | google | openrouter | featherless | openhuman",
  "fallback_chain": [],
  "audit": {
    "caller": "string",
    "repo": "string",
    "human_gate_required": false
  }
}
```

---

## 11. Router Response Contract

```json
{
  "request_id": "uuid",
  "selected_provider": "string",
  "selected_model": "string",
  "route_reason": "string",
  "fallback_used": false,
  "confidence_score": 0,
  "privacy_class": "P0",
  "cost_estimate_usd": 0,
  "latency_ms": 0,
  "output": {
    "type": "text | json | tool_result | error",
    "content": "string"
  },
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  },
  "logs": {
    "policy_checks": [],
    "warnings": [],
    "errors": []
  }
}
```

---

## 12. Proposed Repo Structure

```text
docs/
  pdr/
    PDR-API-ROUTING-OPENHUMAN.md
  routing/
    API_ROUTING_POLICY.md
    PROVIDER_MATRIX.md
    OPENHUMAN_INTEGRATION_BOUNDARY.md

src/
  chromatic_router/
    __init__.py
    router.py
    policy.py
    confidence.py
    privacy.py
    budget.py
    observability.py
    contracts.py
    adapters/
      __init__.py
      base.py
      ollama_adapter.py
      lmstudio_adapter.py
      openai_adapter.py
      anthropic_adapter.py
      google_adapter.py
      openrouter_adapter.py
      featherless_adapter.py
      openhuman_adapter.py
    tests/
      test_policy.py
      test_confidence_gate.py
      test_privacy_gate.py
      test_fallback.py
      test_openhuman_boundary.py

config/
  routing/
    providers.yaml
    routing-table.yaml
    privacy-policy.yaml
    budget-policy.yaml
    openhuman.yaml.example

logs/
  routing/
    .gitkeep
```

---

## 13. Configuration Files

### `config/routing/providers.yaml`

```yaml
providers:
  ollama:
    type: local
    enabled: true
    base_url: http://localhost:11434
    privacy_max: P2

  lmstudio:
    type: local
    enabled: true
    base_url: http://localhost:1234/v1
    privacy_max: P2

  openai:
    type: frontier
    enabled: true
    env_key: OPENAI_API_KEY
    privacy_max: P2

  anthropic:
    type: frontier
    enabled: true
    env_key: ANTHROPIC_API_KEY
    privacy_max: P2

  google:
    type: frontier
    enabled: true
    env_key: GOOGLE_API_KEY
    privacy_max: P2

  openrouter:
    type: broker
    enabled: true
    env_key: OPENROUTER_API_KEY
    privacy_max: P1

  featherless:
    type: broker
    enabled: true
    env_key: FEATHERLESS_API_KEY
    privacy_max: P1

  openhuman:
    type: sidecar
    enabled: false
    base_url: http://127.0.0.1:8787
    env_key: OPENHUMAN_BEARER_TOKEN
    privacy_max: P2
    default_mode: read_only
```

### `config/routing/routing-table.yaml`

```yaml
routes:
  classification:
    default: ollama
    fallback: [lmstudio, featherless]
    max_privacy: P2

  planning:
    default: anthropic
    fallback: [openai, google]
    max_privacy: P2

  coding:
    default: openai
    fallback: [anthropic]
    max_privacy: P1

  review:
    default: anthropic
    fallback: [openai, google]
    max_privacy: P2

  research:
    default: openai
    fallback: [google, anthropic]
    max_privacy: P1

  personal_context:
    default: openhuman
    fallback: [local_vault]
    max_privacy: P2
    human_gate_required: false

  integration_action:
    default: openhuman
    fallback: []
    max_privacy: P2
    human_gate_required: true
```

---

## 14. Implementation Plan

### Phase 0: PDR Commit

Deliverables:

- add this PDR
- create routing config stubs
- create implementation issue/task queue

Done when:

- PDR exists under `docs/pdr/`
- implementation tasks are listed
- no runtime behavior changes yet

### Phase 1: Router Core

Deliverables:

- request/response contract
- policy loader
- confidence gate
- privacy gate
- budget gate
- logging stub
- local mock provider adapter

Done when:

- tests pass for route selection
- P3 data is blocked
- low-confidence requests halt

### Phase 2: Provider Adapters

Deliverables:

- Ollama adapter
- LM Studio adapter
- OpenAI adapter
- Anthropic adapter
- Google adapter
- OpenRouter adapter
- Featherless adapter

Done when:

- each adapter supports a simple text completion contract
- fallback chain works
- provider failures are logged

### Phase 3: OpenHuman Sidecar Read-Only

Deliverables:

- OpenHuman health check
- OpenHuman memory/context query adapter
- feature flag: `OPENHUMAN_ENABLED=false` by default
- read-only enforcement

Done when:

- router can call OpenHuman only when enabled
- OpenHuman cannot perform write actions
- all OpenHuman calls are logged

### Phase 4: Observability + Cost

Deliverables:

- JSONL route log
- provider latency tracking
- token usage tracking where available
- cost estimate table
- daily budget cap

Done when:

- every request produces a structured log entry
- cap breach blocks execution
- fallback usage is visible

### Phase 5: Governed OpenHuman Tool Execution

Deliverables:

- mission packet schema
- human gate enforcement
- integration/tool allowlist
- dry-run mode

Done when:

- OpenHuman tool calls require explicit route policy
- high-risk actions require human gate
- dry-run can preview intended action

---

## 15. Acceptance Criteria

Implementation is complete when all criteria pass.

### Functional

- [ ] All model calls can be made through `ChromaticRouter.route()`.
- [ ] Provider selection is policy-driven, not hardcoded.
- [ ] Fallback works after one provider failure.
- [ ] OpenHuman is disabled by default.
- [ ] OpenHuman can be enabled through config only.
- [ ] OpenHuman read-only mode is enforced.
- [ ] P3 secrets are blocked from all LLM providers.
- [ ] Low-confidence tasks do not route externally.

### Security

- [ ] No API keys are committed.
- [ ] `.env.example` contains placeholder names only.
- [ ] Secrets are loaded from environment variables.
- [ ] Broker providers are blocked from P2+ unless explicitly approved.
- [ ] OpenHuman OAuth/integration actions require human gate.

### Observability

- [ ] Every route logs request ID, task ID, provider, model, latency, estimated cost, fallback, privacy class, confidence score, and result status.
- [ ] Logs are JSONL.
- [ ] Failed routes include error class and fallback decision.

### Tests

- [ ] `test_confidence_gate.py` passes.
- [ ] `test_privacy_gate.py` passes.
- [ ] `test_fallback.py` passes.
- [ ] `test_openhuman_boundary.py` passes.
- [ ] Secret scan passes.

---

## 16. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| OpenHuman beta API changes | High | Medium | adapter isolation + feature flag |
| OAuth data leakage | Medium | High | human gate + allowlist + no default write actions |
| Multiple routers conflict | Medium | High | Chromatic Router remains source of truth |
| Broker sends sensitive data to unknown model | Medium | High | privacy class gate |
| Tool-call explosion | High | Medium | cost/tool budget cap |
| Local model gives weak answer | High | Low-Med | confidence threshold + fallback |
| Secret exposure in prompts | Medium | Critical | P3 classifier + secret scan |
| OpenHuman memory drift | Medium | Medium | no blind bidirectional sync |

---

## 17. Stop Conditions

Stop implementation and escalate if:

- OpenHuman requires broad account permissions before read-only integration is possible
- adapter requires storing API keys outside env/secret manager
- any test reveals P3 secrets can reach an LLM
- provider fallback loops more than once
- router code starts bypassing policy config
- OpenHuman attempts write actions during read-only phase
- implementation requires destructive repo restructuring

---

## 18. Work Queue

| Priority | Task ID | Task | Owner / Model | Output | Stop Condition |
|---:|---|---|---|---|---|
| P1 | ROUTE-001 | Commit PDR and config stubs | ChatGPT/Codex | PDR + YAML skeletons | repo paths unclear |
| P1 | ROUTE-002 | Build router contracts | Codex | `contracts.py` | schema ambiguity |
| P1 | ROUTE-003 | Build confidence/privacy gates | Codex | gate modules + tests | P3 not blockable |
| P1 | ROUTE-004 | Build mock/local adapter | Codex | base adapter + mock | interface unstable |
| P1 | ROUTE-005 | Add provider YAML loader | Codex | config loader | config conflicts |
| P2 | ROUTE-006 | Add cloud provider adapters | Codex | adapters | SDK/auth failures |
| P2 | ROUTE-007 | Add fallback engine | Codex | fallback tests | looping risk |
| P2 | ROUTE-008 | Add OpenHuman health/read-only adapter | Codex/ChatGPT | sidecar adapter | write action required |
| P2 | ROUTE-009 | Add JSONL observability | Codex | route logs | sensitive logging risk |
| P3 | ROUTE-010 | Governed OpenHuman tool execution | Claude/ChatGPT/Codex | mission packet + gate | OAuth risk unclear |

---

## 19. Agent Handoff: Implementation

# Agent Handoff: Implement Chromatic API Router + OpenHuman Sidecar

## Role

You are acting as a repo implementer.

## Objective

Implement the first safe version of the Chromatic API Router according to `docs/pdr/PDR-API-ROUTING-OPENHUMAN.md`.

## Inputs

- `docs/pdr/PDR-API-ROUTING-OPENHUMAN.md`
- `config/routing/providers.yaml`
- `config/routing/routing-table.yaml`
- existing repo standards
- existing `.env.example`

## Instructions

1. Create router package structure under `src/chromatic_router/`.
2. Implement request/response schemas.
3. Implement confidence gate.
4. Implement privacy gate.
5. Implement budget gate stub.
6. Implement policy-based provider selection.
7. Implement mock adapter first.
8. Add OpenHuman adapter as disabled/read-only by default.
9. Add JSONL logging with redaction.
10. Write tests for gate behavior and OpenHuman boundary.

## Acceptance Criteria

- Router can select a provider from YAML config.
- Router blocks P3 data.
- Router blocks external calls below confidence 60.
- OpenHuman is disabled by default.
- OpenHuman route fails closed unless explicitly enabled.
- Tests pass.
- No secrets are committed.

## Stop Conditions

Stop and report back if:

- repo language/runtime differs from assumed Python implementation
- provider SDKs are not installed and installing them would change project scope
- OpenHuman requires write/OAuth access for basic read-only operation
- test framework is unknown
- implementation requires editing unrelated architecture files

---

## 20. Final Decision

Proceed with implementation using this order:

```text
PDR -> config stubs -> router contracts -> gates -> mock adapter -> provider adapters -> OpenHuman read-only adapter -> observability -> governed OpenHuman tool execution
```

The first implementation milestone is not “OpenHuman does everything.”

The first milestone is:

```text
One router. One policy. One log trail. OpenHuman safely reachable, disabled by default, read-only when enabled.
```
