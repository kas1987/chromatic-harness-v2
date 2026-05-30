# PDR-CHV2-001: Pre-Session Context and Execution Flow Consolidation

## 0. Metadata

| Field | Value |
|---|---|
| PDR ID | PDR-CHV2-001 |
| System | Chromatic Harness v2 |
| Domain | Pre-session context, agent operations, routing, beads, governance |
| Status | Draft for implementation |
| Priority | P0 |
| Owner | Chromatic Harness Orchestrator |
| Target Repos | Harness v2 repo; related Chromatic Wiki canon repo |
| Created | 2026-05-29 |

---

## 1. Executive Summary

Chromatic Harness v2 already contains strong operating components: `AGENT_OPERATIONS.md`, beads (`bd`), session compact, MCP hygiene, routing architecture, deployment console, magnets, and provider selection. The current weakness is that these systems are not yet expressed as one unified boot-and-execute flow.

This PDR creates the missing consolidation layer: a canonical execution flow, a pre-session context policy, a beads object model, an OpenRouter broker policy, and a router validation backlog.

The goal is simple: agents should not infer owner intent from scattered context. Agents should execute from explicit artifacts.

---

## 2. Problem Statement

Current Harness v2 docs are strong but distributed across multiple entrypoints. `AGENTS.md`, `CLAUDE.md`, and `AGENT_OPERATIONS.md` duplicate important rules around beads, session compact, MCP hygiene, and session completion.

This creates five problems:

1. **Context bloat** — agents may load repeated instructions.
2. **Drift risk** — duplicated rules can diverge.
3. **Ambiguous pre-session loading** — agents do not know which docs are mandatory vs conditional.
4. **Beads ambiguity** — `bd` issues, runtime beads, magnet beads, learning beads, and canon candidates need a shared object model.
5. **OpenRouter ambiguity** — OpenRouter is listed as a fallback provider but not fully governed as a broker.

---

## 3. Goals

### Primary Goals

- Create a canonical execution flow for Harness v2.
- Define what loads into pre-session context by default.
- Separate mandatory context from optional/deep context.
- Define beads object types and promotion paths.
- Formalize OpenRouter as a governed broker/fallback layer.
- Create router validation beads for implementation.
- Reduce duplicated instructions across `AGENTS.md` and `CLAUDE.md`.

### Non-Goals

- This PDR does not implement router code directly.
- This PDR does not change provider keys or secrets.
- This PDR does not replace beads (`bd`) as the source of work truth.
- This PDR does not remove Claude/Cursor-specific instructions; it consolidates them.

---

## 4. Current Flow Summary

Current intended flow:

```text
Session Start
  -> read latest handoff
  -> bd prime / bd ready
  -> git branch/status
  -> log context entering session
  -> audit MCP context
  -> select task
  -> classify complexity
  -> route provider
  -> execute bounded mission
  -> emit magnets/beads/logs
  -> validate
  -> commit/push
  -> compact/handoff
```

This is correct, but it needs one canonical map that all agents can follow.

---

## 5. Proposed Artifacts

This PDR creates the following files:

| File | Purpose |
|---|---|
| `00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md` | One-page canonical flow from pre-session to handoff. |
| `docs/governance/PRE_SESSION_CONTEXT_POLICY.md` | Tiered context loading policy. |
| `docs/BEADS_OBJECT_MODEL.md` | Defines bd issues, runtime beads, magnet beads, learning beads, handoff beads, canon beads. |
| `docs/governance/OPENROUTER_BROKER_POLICY.md` | Defines OpenRouter usage, privacy blocks, fallback order, cost caps, and logging. |
| `beads/ROUTER_VALIDATION_BEADS.md` | Copy-ready beads issue backlog for router validation. |
| `AGENTS_WRAPPER_PROPOSAL.md` | Proposed reduced `AGENTS.md` wrapper. |
| `CLAUDE_WRAPPER_PROPOSAL.md` | Proposed reduced `CLAUDE.md` wrapper. |

---

## 6. Target Architecture

### 6.1 Canonical Execution Flow

```text
Pre-session context boot
  -> Work discovery via beads
  -> Mission packet creation
  -> Governance gates
  -> Complexity classification
  -> Provider routing
  -> Bounded execution
  -> Magnet observation
  -> Beads update
  -> Validation
  -> Commit/push/sync
  -> Session compact handoff
```

### 6.2 Pre-Session Context Tiers

| Tier | Name | Auto-load? | Contents |
|---|---|---:|---|
| P0 | Boot minimum | Yes | latest handoff pointer, git status, bd ready summary, MCP summary |
| P1 | Active work | Conditional | selected bead, RPI packet, scoped files |
| P2 | Governance | Conditional | agent ops, routing policy, MCP policy |
| P3 | Deep architecture | No | deployment guide, playbooks, detailed docs |
| P4 | Archive/history | Never by default | old logs, old handoffs, historical traces |

### 6.3 Beads Object Path

```text
Magnet event
  -> runtime bead
  -> bd issue if actionable
  -> learning bead if reusable
  -> canon candidate if durable
  -> canon registry if approved
```

### 6.4 OpenRouter Broker Role

OpenRouter should be governed as a broker, not a casual provider.

```text
Local Ollama / LM Studio
  -> Remote Ollama desktop
  -> Direct provider API
  -> OpenRouter broker fallback
  -> RunPod / premium provider
```

OpenRouter must respect privacy class, budget, model allowlist, and logging requirements.

---

## 7. Implementation Plan

### Phase 1 — Governance Artifacts

1. Add `HARNESS_EXECUTION_FLOW.md`.
2. Add `PRE_SESSION_CONTEXT_POLICY.md`.
3. Add `BEADS_OBJECT_MODEL.md`.
4. Add `OPENROUTER_BROKER_POLICY.md`.

### Phase 2 — Instruction Deduplication

1. Reduce `AGENTS.md` to a wrapper pointing to `AGENT_OPERATIONS.md`.
2. Reduce `CLAUDE.md` to a Claude-specific wrapper.
3. Keep Beads integration generated block only if hash-verified and intentionally duplicated.
4. Ensure CI checks required links remain.

### Phase 3 — Router Validation Beads

Create beads for:

- ROUTE-001: context detector tests
- ROUTE-002: complexity classifier 50-case suite
- ROUTE-003: provider selector matrix tests
- ROUTE-004: remote Ollama probe
- ROUTE-005: OpenRouter adapter policy
- ROUTE-006: privacy gate for cloud providers
- ROUTE-007: pre-session manifest generation
- ROUTE-008: MCP context budget test

### Phase 4 — Validation

Run:

```bash
python scripts/check_agent_operations.py
python scripts/generate_pre_session_inventory.py
python scripts/audit_mcp_context.py --profile harness_dev
pytest tests/test_context_*.py tests/test_pre_session_inventory_script.py
```

If router code is changed, also run:

```bash
pytest tests/test_router_*.py tests/test_provider_selector*.py tests/test_complexity_classifier*.py
```

---

## 8. Acceptance Criteria

- [x] `HARNESS_EXECUTION_FLOW.md` exists and is linked from `AGENT_OPERATIONS.md`.
- [x] `PRE_SESSION_CONTEXT_POLICY.md` exists and defines tiered loading.
- [x] `BEADS_OBJECT_MODEL.md` exists and separates bd issues from runtime/learning/canon beads.
- [x] `OPENROUTER_BROKER_POLICY.md` exists and defines privacy/cost/model restrictions.
- [x] Router validation beads are created or imported (epic `chromatic-harness-v2-15x`, children `15x.1`–`15x.8`).
- [x] `AGENTS.md` and `CLAUDE.md` are hybrid wrappers (Beads block preserved).
- [ ] CI guard still passes (run `check_agent_operations.py` + pytest).
- [ ] Pre-session context can be summarized into a small manifest (`15x.7`).

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agents continue loading all docs | Token waste, confusion | Enforce pre-session tiers and context report logging. |
| Duplicated docs drift | Conflicting instructions | Make `AGENT_OPERATIONS.md` canonical and wrappers thin. |
| OpenRouter sends private context to cloud | Data exposure | Add privacy class blocks and logging. |
| Beads terminology confuses agents | Bad state transitions | Add object model and promotion rules. |
| Router remains unvalidated | Wrong providers/cost burn | Create validation beads and tests before production use. |

---

## 10. Decision Record

| Decision | Rationale |
|---|---|
| Keep `AGENT_OPERATIONS.md` canonical | It is already the strongest operational checklist. |
| Use wrappers for `AGENTS.md` and `CLAUDE.md` | Reduces duplication while preserving agent entrypoints. |
| Formalize OpenRouter as broker | It can route many providers but must be governed. |
| Treat pre-session context as tiered | Prevents automatic context flooding. |
| Define beads object model | Prevents bd/runtime/dashboard/canon confusion. |

---

## 11. Next Action

Open a PR that adds the included files, then create/import the router validation beads.

Suggested branch:

```bash
git checkout -b pdr/chv2-pre-session-flow
```

Suggested commit:

```bash
git add .
git commit -m "Add PDR for pre-session context and execution flow consolidation"
```
