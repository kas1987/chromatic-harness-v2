# PDR: Chromatic BEADS Pipeline for Knowledge Intake and Agent Execution

## 0. Executive Summary

This PDR defines a **BEADS Pipeline** for Chromatic Harness: a structured intake and execution system where every unit of work becomes a traceable "bead" that can be scored, routed, executed, validated, and logged.

The pipeline supports three runtime modes:

1. **Cloud-routed mode** through OpenRouter for flexible model access.
2. **Hybrid fallback mode** using OpenRouter first, then local models through Ollama or LM Studio.
3. **Offline/local mode** using only local models and local storage.

The goal is to stop relying on agents to infer hidden intent. Instead, agents operate from explicit artifacts: PDRs, workflows, schemas, queues, canon registries, source reliability scores, and execution logs.

---

## 1. PDR Metadata

| Field | Value |
|---|---|
| PDR ID | PDR-CHROMATIC-BEADS-001 |
| Project | Chromatic Knowledge Operating System |
| Repo | `kas1987/chromatic-wiki` |
| Status | Draft |
| Owner | Human Owner / Chromatic Architect |
| Primary Runtime | OpenRouter |
| Redundancy Runtime | Ollama / LM Studio / local OpenAI-compatible server |
| Core Pattern | Intake -> Bead -> Score -> Route -> Execute -> Validate -> Promote/Archive |

---

## 2. Problem Statement

Chromatic Harness is reaching a scale where informal prompting and implicit intent are no longer safe or efficient.

Current risks:

- Agents assume intent instead of reading explicit contracts.
- Knowledge gets dumped into repos without quality gates.
- External docs, guides, and repo learnings become noisy context.
- Work items are not always traceable from source to execution.
- Cloud model availability, cost, and outages can block progress.
- Offline capability is limited unless a fallback path is designed up front.

This PDR creates a durable pipeline where every piece of knowledge or execution work is wrapped as a **bead**: a structured, traceable, reviewable unit.

---

## 3. Core Concept: BEADS

For Chromatic, **BEADS** means:

> **Bounded Evidence-backed Agentic Decision Sequence**

A bead is a single structured unit of knowledge, decision, task, or execution output.

Each bead must be:

- **Bounded**: small enough for one agent/model to understand.
- **Evidence-backed**: linked to source, context, or prior bead.
- **Agent-readable**: formatted for execution or review.
- **Decision-aware**: includes status, confidence, and routing.
- **Sequentially traceable**: linked to parent/child beads.

---

## 4. Pipeline Overview

```text
Source Material
  -> Intake Bead
  -> Classification Bead
  -> Scoring Bead
  -> Extraction Bead
  -> Candidate Bead
  -> Execution Bead
  -> Review Bead
  -> Canon / Archive Bead
```

The pipeline works for both knowledge and work execution.

### Knowledge Example

```text
Claude Architect Guide
  -> Source Intake Bead
  -> Reliability Score Bead
  -> Pattern Extraction Bead
  -> Canon Candidate Bead
  -> Approved Agent Architecture Standard
```

### Execution Example

```text
User says "GO"
  -> Queue Selection Bead
  -> Confidence Score Bead
  -> Model Routing Bead
  -> Execution Bead
  -> Validation Bead
  -> Decision Log Bead
```

---

## 5. Target Architecture

```text
/00_RAW
  External sources, dumps, notes, PDFs, repo snapshots

/01_INDEX
  Source index, topic index, bead registry

/02_INTAKE
  Intake beads and intake templates

/03_CANDIDATES
  Extracted patterns and canon candidates

/04_CANON
  Approved Chromatic standards

/05_PDRS
  Project Design Records

/06_PLAYBOOKS
  Repeatable operating rules

/07_WORKFLOWS
  Execution and automation workflows

/08_AGENT_ARCHITECTURE
  Agent roles, routing rules, competency models

/09_RESEARCH
  Research summaries, comparison matrices, source reviews

/10_ARCHIVE
  Deprecated, rejected, superseded, parked material
```

---

## 6. Bead Object Schema

```json
{
  "bead_id": "BEAD-000001",
  "type": "intake | score | extract | task | execution | review | canon | archive",
  "title": "Short human-readable title",
  "status": "new | scored | routed | active | review | approved | rejected | archived",
  "source": {
    "kind": "github | pdf | web | note | issue | conversation | repo",
    "uri": "source location",
    "captured_at": "YYYY-MM-DD"
  },
  "parent_beads": [],
  "child_beads": [],
  "summary": "What this bead contains",
  "evidence": [],
  "confidence_score": 0,
  "reliability_score": 0,
  "chromatic_fit_score": 0,
  "risk_level": "low | medium | high | critical",
  "routing": {
    "preferred_model": "openrouter/model-name",
    "fallback_model": "local/model-name",
    "mode": "cloud | hybrid | offline"
  },
  "required_output": "Exact output expected",
  "acceptance_checks": [],
  "stop_conditions": [],
  "result": null,
  "review": null,
  "created_by": "human | agent | automation",
  "created_at": "YYYY-MM-DDTHH:MM:SSZ",
  "updated_at": "YYYY-MM-DDTHH:MM:SSZ"
}
```

---

## 7. Runtime Modes

### 7.1 Cloud-Routed Mode: OpenRouter First

Use when:

- Current best model quality matters.
- Multiple model families should be compared.
- Internet/cloud access is available.
- Cost is acceptable.

Flow:

```text
Task Bead -> Router -> OpenRouter -> Model -> Result Bead -> Review
```

Recommended routing:

| Task | Preferred Model Class |
|---|---|
| Long synthesis | Claude-family through OpenRouter |
| Structured planning | GPT/Claude-family through OpenRouter |
| Code implementation | coding-specialized model |
| Research summarization | broad-context model |
| Cheap triage | lower-cost fast model |

### 7.2 Hybrid Redundancy Mode

Use when:

- Cloud model may fail.
- Cost needs control.
- Privacy varies by bead.
- Execution should continue despite provider outage.

Flow:

```text
Try OpenRouter
  if fail/cost/privacy block:
    try local OpenAI-compatible endpoint
  if fail:
    quarantine bead
```

### 7.3 Offline Local Mode

Use when:

- Internet is unavailable.
- Sensitive material should stay local.
- Bulk summarization/classification is needed cheaply.
- Lower-quality but private execution is acceptable.

Local backends:

- Ollama
- LM Studio
- llama.cpp server
- vLLM/SGLang if running larger local infrastructure

Flow:

```text
Task Bead -> Local Router -> Local Model -> Result Bead -> Local Review -> Sync Later
```

---

## 8. OpenRouter Provider Abstraction

All model calls should go through a provider adapter.

```text
Agent Task
  -> provider_adapter.generate()
      -> OpenRouterAdapter
      -> OllamaAdapter
      -> LMStudioAdapter
      -> MockAdapter for tests
```

No workflow should hardcode a single provider.

### Required Adapter Interface

```python
class ModelProvider:
    def generate(self, task, model, temperature, max_tokens, tools=None):
        pass

    def healthcheck(self):
        pass

    def estimate_cost(self, task, model):
        pass
```

---

## 9. Execution Loop

```text
Observe -> Select Bead -> Score -> Route -> Execute -> Validate -> Log -> Next Bead
```

### Required stop conditions

Stop if:

- Confidence < 60.
- Required source is missing.
- Model output fails validation twice.
- Task requires destructive repo action.
- Cost estimate exceeds budget.
- Bead requests access to forbidden context.
- Local/offline mode lacks capable model.

---

## 10. Confidence Gate

| Score | Band | Allowed Action |
|---:|---|---|
| 90-100 | Very high | Execute and log |
| 75-89 | High | Execute with validation |
| 60-74 | Medium | Execute only if reversible |
| 40-59 | Low | Plan only |
| 0-39 | Blocked | Halt/quarantine |

---

## 11. Source Reliability Gate

| Tier | Meaning | Allowed Use |
|---|---|---|
| Tier 1 | Canon-worthy | Can support canon |
| Tier 2 | Strong evidence | Can support candidates |
| Tier 3 | Useful but unverified | Research only |
| Tier 4 | Experimental | Parked or sandbox |
| Tier 5 | Archive only | Do not route to agents |

---

## 12. Folder Deliverables

This PDR should create or inform:

```text
/05_PDRS/PDR_CHROMATIC_BEADS_PIPELINE.md
/02_INTAKE/BEAD_TEMPLATE.json
/02_INTAKE/BEAD_TEMPLATE.md
/07_WORKFLOWS/OPENROUTER_EXECUTION_WORKFLOW.md
/07_WORKFLOWS/OFFLINE_FALLBACK_WORKFLOW.md
/08_AGENT_ARCHITECTURE/MODEL_ROUTING_GUIDE.md
/01_INDEX/BEAD_REGISTRY.json
```

---

## 13. Work Queue

| Priority | Task | Owner / Model | Inputs | Output | Stop Condition |
|---:|---|---|---|---|---|
| P0 | Create repo folder architecture | Cartographer / Janitor | WK-013 | `REPO_STRUCTURE.md` | Folder rules unclear |
| P0 | Create bead schema | Auditor | This PDR | `BEAD_TEMPLATE.json` | Schema cannot validate |
| P0 | Create provider abstraction | Builder/Codex | Adapter interface | Python provider module | Secrets required |
| P1 | Create OpenRouter workflow | Builder | API docs/env vars | Workflow doc + stub | No API key |
| P1 | Create local fallback workflow | Builder | Ollama/LM Studio config | Offline workflow doc | No local model installed |
| P1 | Create bead registry | Archivist | Schema | `BEAD_REGISTRY.json` | Registry format disputed |
| P2 | Add validation scripts | Auditor | Schema | `validate_bead.py` | Missing test data |
| P2 | Add routing scorecard | Financier/Auditor | Model list | Model routing matrix | Pricing unavailable |

---

## 14. Recommended Minimal Implementation

### Environment variables

```bash
OPENROUTER_API_KEY="..."
OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
LOCAL_OPENAI_BASE_URL="http://localhost:11434/v1"
DEFAULT_CLOUD_MODEL="anthropic/claude-sonnet-4"
DEFAULT_LOCAL_MODEL="qwen2.5-coder:7b"
CHROMATIC_MODE="hybrid"
```

### Minimal provider routing logic

```text
if CHROMATIC_MODE == cloud:
  use OpenRouter only

if CHROMATIC_MODE == hybrid:
  try OpenRouter
  fallback to local
  quarantine on repeated failure

if CHROMATIC_MODE == offline:
  use local only
  queue cloud-only beads for later
```

---

## 15. Validation Requirements

A bead result is valid only if:

- It matches the requested output format.
- It cites or links source material when applicable.
- It records model used.
- It records confidence.
- It records validation result.
- It updates parent/child relationships.
- It does not promote raw knowledge directly into canon.

---

## 16. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Context dump returns | High | Agents may only consume scored/candidate/canon beads |
| Provider outage | Medium | Hybrid/local fallback |
| Local model weak output | Medium | Use local for triage, not final canon unless reviewed |
| Cost runaway | High | Budget gate before cloud calls |
| Untrusted source promoted | High | Source reliability framework |
| Agent loops | High | Max retries and quarantine |
| Hidden owner intent | High | Require PDR/workflow/bead inputs |

---

## 17. Success Criteria

The pipeline is successful when:

- Every intake source becomes a bead.
- Every execution task becomes a bead.
- Every model response is traceable.
- Every canon promotion has evidence.
- Every failed task is quarantined, not retried forever.
- OpenRouter and local fallback can use the same task schema.
- Agents can execute without guessing the owner's hidden intent.

---

## 18. Next Execution Step

Create the first implementation artifacts:

1. `BEAD_TEMPLATE.json`
2. `BEAD_TEMPLATE.md`
3. `OPENROUTER_EXECUTION_WORKFLOW.md`
4. `OFFLINE_FALLBACK_WORKFLOW.md`
5. `BEAD_REGISTRY.json`

Then open a PR linking this PDR to WK-013, WK-014, WK-016, WK-017, WK-018, and WK-019.
