# Chromatic Harness v2.0 — Architecture Gaps & Ecosystem Landscape

## Executive Summary

This document maps the seven architecture gaps identified in the Chromatic Harness v2.0 pipeline diagram against the current repository state and the broader open-source / research ecosystem. For each gap it records: what the v2.0 diagram specifies, what currently exists in the repository, what the ecosystem offers (with tool names, repository links, and key papers), and concrete implementation recommendations.

The v2.0 pipeline defines a complete autonomous execution loop — `INTENT → MISSION PACKET (CMP) → PLAN & DECOMPOSE (ADK) → EXECUTE (AGENTS) → MAGNETS OBSERVE & COLLECT → SCORE & VALIDATE (CMP) → DECIDE & CONTINUE OR COMPLETE` — backed by a Magnets observability layer, an Agent Lead synthesis layer, an MCP tool-connectivity layer, and an Auto-Intake-to-Beads handoff mechanism. The architecture is well-validated by the ecosystem; all seven gaps have mature reference implementations to draw from.

**Bottom line:** The harness has a solid foundation (router, gates, memory, magnets spec, 53/53 tests). What is missing is the connective tissue: MCP servers that actually run, a full 7-magnet runtime coordinator, an agent workflow graph, a two-log audit system, a self-healing confidence gate, and the auto-intake pipeline that feeds goals into beads as atomic tasks.

**Consolidation epic (close loops first):** See [V2_CONSOLIDATION_BEADS.md](./V2_CONSOLIDATION_BEADS.md) — bead `chromatic-harness-v2-h24`.

---

## Current Repo State

As of 2026-05-28 the following components exist and are functional:

| Layer | Status | Key Files |
|---|---|---|
| Multi-provider router | **Complete** | `02_RUNTIME/router/router.py`, `router/adapters/` (12 adapters) |
| Privacy / Budget / Confidence gates | **Complete** | `02_RUNTIME/router/gate.py`, `02_RUNTIME/cmp-bridge/confidence-gate.ts` |
| Policy loader | **Complete** | `02_RUNTIME/router/policy.py` |
| System memory store | **Complete** | `02_RUNTIME/memory/store.py` (SQLite/aiosqlite; governance rules, learnings, sessions) |
| Scope enforcer + dispatch guard | **Complete** | `02_RUNTIME/scope/enforcer.py`, `scope/guard.py` |
| Magnets — Python runtime stubs | **Partial** | `02_RUNTIME/magnets/` — 8 magnets (intent, memory, scope, security, validation, execution, cost, confidence) as Python classes |
| Magnets — TypeScript stubs | **Partial** | `02_RUNTIME/magnets/` — base, confidence, cost, execution, synthesis in TS |
| CMP bridge | **Complete** | `02_RUNTIME/cmp-bridge/cmp-executor.ts`, `intent-gate.ts`, `scope-gate.ts` |
| Orchestrator | **Stub** | `02_RUNTIME/orchestrator/orchestrator.py` (5.4 KB — basic mission coordination) |
| FastAPI runtime API | **Complete** | `02_RUNTIME/api/main.py` |
| Frontend console | **Complete** | `05_FRONTEND_CONSOLE/` (Next.js) |
| MCP tool manifest | **Doc only** | `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md` — spec exists, no server code |
| Agent Lead layer | **Doc only** | `03_AGENTS/agent_lead.md` — spec exists, no code |
| Agent Workflow Graph | **Not started** | No Scout, Builder, Auditor, Scribe, or Gate agents |
| Auto-Intake to Beads | **Not started** | Manual issue creation only (`beads-bridge.ts` exists as foundation) |
| Two-Log Model (execution + trace) | **Partial** | `02_RUNTIME/router/observability.py` (2.7 KB stub), `07_LOGS_AND_AUDIT/routing/*.jsonl` (router only) |
| Confidence Gate v2 + Self-Heal | **Partial** | Gate scoring exists; no retry/decompose/self-heal logic |
| Autonomy Levels (L0–L5) | **Not started** | Referenced in v2 diagram; no implementation |
| Playbook Evolution / Feedback Loop | **Not started** | Static playbooks in `04_PLAYBOOKS/`; no feedback mechanism |

The test suite is at 53/53 passing. The protocol specs in `01_PROTOCOLS/` (BEADS, CMP, MAGNETS, MCP schemas) are well-written and should be treated as the source of truth for any new implementation.

---

## Gap 1: Full Magnets Layer (Observability & Inflection Points)

### What the v2.0 Diagram Specifies

The Magnets Layer is the observability and inflection-point substrate of the entire pipeline. Seven named magnets sit at key transitions: **Intake**, **Plan**, **Dispatch**, **Execution**, **Validation**, **Decision**, and **Closure**. Each magnet fires on a trigger event, captures structured telemetry, and feeds a six-stage feedback pipeline: `COLLECT → NORMALIZE → CORRELATE → SCORE → FEEDBACK → RECOMMEND`.

The diagram specifies Magnets Capabilities: real-time visibility, inflection logging, confidence scoring, audit capture, pattern recognition, quality scaling. Magnets Principles: lightweight & fast, non-blocking, normalized output, pluggable, real-time capture, reusable templates.

### Current Repo State

Eight Python magnet classes exist in `02_RUNTIME/magnets/`: `intent_magnet.py`, `memory_magnet.py`, `scope_magnet.py`, `security_magnet.py`, `validation_magnet.py`, `execution_magnet.py`, `cost_magnet.py`, `confidence_magnet.py`. TypeScript counterparts exist for base, confidence, cost, execution, and synthesis. The spec is fully defined in `01_PROTOCOLS/MAGNETS/MAGNETS_SPEC.md`, `magnet_event.schema.json`, and `inflection_points.yaml`. A `magnet-synthesis.ts` file exists.

**Gap:** The magnets are implemented as individual Python/TS classes but the six-stage pipeline (`COLLECT → NORMALIZE → CORRELATE → SCORE → FEEDBACK → RECOMMEND`) has no runtime coordinator. The **Intake** and **Closure** magnets (the pipeline bookends) are missing. There is no `MagnetOrchestrator` that wires them together into a running observability stream.

### Ecosystem Findings

| Tool / Paper | Key Contribution | Link |
|---|---|---|
| **AgentTrace** (arxiv 2602.10133) | 3-surface taxonomy: cognitive (reasoning chain), operational (tool invocations), contextual (memory access). Minimal-overhead dynamic observability. Execution log = full state rebuild. | [arxiv.org/pdf/2602.10133](https://arxiv.org/pdf/2602.10133) |
| **OpenTelemetry GenAI semconv 1.29+** | Stable `gen_ai.*` attribute namespace: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.response.finish_reason`. Tool call spans under `gen_ai.tool.call`. | [opentelemetry.io/docs/specs/semconv/gen-ai/](https://opentelemetry.io/docs/specs/semconv/gen-ai/) |
| **Zylos Research — Two-Log Model** | (1) Execution log for recovery: workflow state transitions, model-call request/response hashes, tool invocations, idempotency keys, approvals, retries, side-effect receipts, artifact hashes, prompt versions. (2) Observability trace for diagnostics: OTel spans, token usage, latency, errors, annotations, evaluation results. | [zylos.ai/research/2026-04-29-agent-observability-production-debugging](https://zylos.ai/research/2026-04-29-agent-observability-production-debugging) |
| **Laminar** | Open-source, OTel-native. Captures every LLM call, tool invocation, retrieval step, sub-agent handoff. Fully open-source alternative to LangSmith. | [laminar.sh/article/agent-observability](https://laminar.sh/article/agent-observability) |
| **Braintrust** | Structured tracing, nested agent spans, production trace scoring. 1M free trace spans/month. High-quality span visualization. | [braintrust.dev/articles/agent-observability-complete-guide-2026](https://braintrust.dev/articles/agent-observability-complete-guide-2026) |
| **Databricks Unity Catalog OTel** | Serverless OTLP ingestion to Delta tables. Real-time, long-term retention, PII governance, SQL analytics over traces. | [databricks.com/blog/observability-any-agent-anywhere-production-ready-tracing-opentelemetry-unity-catalog](https://databricks.com/blog/observability-any-agent-anywhere-production-ready-tracing-opentelemetry-unity-catalog) |
| **REGAL (Adobe, arxiv 2603.03018)** | Deterministic telemetry as first-class primitive. Medallion ELT pipeline (Bronze → Silver → Gold artifacts). Declarative metrics registry. Version-controlled action space. | [arxiv.org/pdf/2603.03018](https://arxiv.org/pdf/2603.03018) |

**Key Insight:** The v2.0 `COLLECT → NORMALIZE → CORRELATE → SCORE → FEEDBACK → RECOMMEND` pipeline maps directly to the Zylos Two-Log Model. The existing magnet classes are the **collection** layer. The missing pieces are normalization (to OTel GenAI semconv), correlation (cross-magnet span stitching), and the scoring/feedback/recommend pipeline.

### Implementation Recommendations

1. **Create `MagnetOrchestrator`** (`02_RUNTIME/magnets/magnet_orchestrator.py`): registers all 7 magnets, routes events through the `COLLECT → NORMALIZE → CORRELATE → SCORE → FEEDBACK → RECOMMEND` pipeline. Make it non-blocking (asyncio event queue).
2. **Add `intake_magnet.py` and `closure_magnet.py`** to complete the 7-magnet set. Intake fires on `bd create` / goal arrival. Closure fires on `bd close` / mission complete.
3. **Normalize to OTel GenAI semconv**: each magnet's output should produce a span conforming to `gen_ai.*` attributes. Use the `opentelemetry-sdk` Python package.
4. **Implement Two-Log Model** (see also Gap 6): execution log as append-only JSONL in `07_LOGS_AND_AUDIT/execution/`; observability trace exported via OTLP to a local Laminar or Braintrust endpoint.
5. **Reference the REGAL Bronze → Silver → Gold pattern** for the scoring/feedback phase: raw magnet events (Bronze) → normalized OTel spans (Silver) → scored artifacts with recommendations (Gold).

---

## Gap 2: MCP Tool & Context Layer

### What the v2.0 Diagram Specifies

A full **MCP Layer (Tool & Context Connectivity)** with 8 categories:

| Category | Examples |
|---|---|
| Git / GitHub | Repos, PRs, commits, branches |
| Filesystem | Read, write, search, Bash |
| Database | SQLite, Postgres, query tools |
| Web / Search | Search, fetch, summarize |
| Terminal / Shell | Run commands, scripts |
| Calendar / Email | Schedule, notify, send |
| LLM / Model Providers | Claude, OpenAI, Ollama |
| 3rd Party APIs | Custom MCP servers |

The diagram labels this as the **Model Context Protocol (MCP) — Connectivity & Tools** layer and notes it works with any model/framework.

### Current Repo State

`01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md` exists as a specification document. **No MCP server code exists in the repository.** The router communicates with providers via direct HTTP adapters (`02_RUNTIME/router/adapters/`). There is no MCP client, no MCP server, and no `mcp.json` or `claude_desktop_config.json` configuration.

### Ecosystem Findings

| Tool | Stars | Key Capability | Link |
|---|---|---|---|
| **MCP official Python SDK** | 23k+ | Full client + server support. Stdio, SSE, Streamable HTTP transports. MIT licensed. | [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) |
| **MCP Reference Servers** | — | Filesystem (access controls), Git (read/search/manipulate), Memory (knowledge graph), Fetch (web), Sequential Thinking, PostgreSQL, SQLite, Brave Search | [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) |
| **MCP Specification 2025-11-05 (stable)** | — | JSON-RPC 2.0. Hosts ↔ Clients ↔ Servers. Resources, Tools, Prompts. Roots, Sampling. | [modelcontextprotocol.io/specification/2025-11-05](https://modelcontextprotocol.io/specification/2025-11-05) |
| **MCP Specification 2026-07-28 RC** | — | Stateless core, removes initialize handshake, `_meta` metadata, `Mcp-Method`/`Mcp-Name` headers, Extensions framework (MCP Apps, Tasks) | [modelcontextprotocol.io/specification/2026-07-28-release-candidate](https://modelcontextprotocol.io/specification/2026-07-28-release-candidate) |
| **FastMCP** | — | Zero-config server generation. Decorate a Python function, get an MCP tool. | [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp) |
| **MCPGuardian / MCPProxy** | — | Enterprise gateway: RBAC, audit trails, automatic quarantine, intelligent discovery | [github.com/mcp-guardian](https://github.com/mcp-guardian) |
| **ProjectSync MCP** | — | Unifies Linear, Jira, GitHub Issues, Asana. 13 tools: create_issue, sprint_management, backlog_grooming, workflow_automation | registry.modelcontextprotocol.io |
| **REGAL (Adobe)** | — | Registry-driven tool architecture. Declarative metrics registry → compilation layer synthesizes MCP tools. "Interface-as-code." Mitigates tool drift. | [arxiv.org/pdf/2603.03018](https://arxiv.org/pdf/2603.03018) |
| **MCP Registry** | — | Searchable catalog of 3,000+ MCP servers | [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) |
| **Glama / MCP.so / PulseMCP** | — | Community registries with search and reviews | [glama.ai/mcp/servers](https://glama.ai/mcp/servers) · [mcp.so](https://mcp.so) |

**Key Insight:** MCP is now the canonical standard for tool connectivity. The v2.0 diagram's 8 tool categories all have reference implementations in `github.com/modelcontextprotocol/servers`. The fastest path is: (1) implement a **Chromatic MCP Server** using FastMCP that exposes the router, memory store, scope enforcer, and beads bridge as MCP tools; (2) wire the Claude-family adapters to use MCP over Stdio or SSE instead of the current direct HTTP.

### Implementation Recommendations

1. **Chromatic MCP Server** (`02_RUNTIME/mcp/chromatic_mcp_server.py`): Use FastMCP to expose these tools:
   - `route_request(messages, budget, privacy_level)` → wraps `router.py`
   - `memory_store(key, value, scope)` → wraps `memory/store.py`
   - `scope_check(agent_id, action)` → wraps `scope/enforcer.py`
   - `beads_create(title, description, type)` → wraps `beads-bridge.ts` or `bd` CLI
   - `magnet_event(magnet_name, payload)` → wraps the magnet pipeline
2. **Register reference servers** in `09_DEPLOYMENT/config/mcp.json`: filesystem, git, fetch, sqlite (from `modelcontextprotocol/servers`).
3. **Add MCP client** to the orchestrator: `02_RUNTIME/orchestrator/mcp_client.py` — connects to the Chromatic MCP server and any registered external servers.
4. **Follow REGAL "interface-as-code" pattern**: maintain `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md` as the declarative registry; generate FastMCP tool decorators from it via a compilation step.
5. **Use MCPGuardian** for production: add RBAC so agents can only call tools within their granted scope (connects to `scope/enforcer.py`).

---

## Gap 3: Agent Lead / Synthesis & Decision Layer

### What the v2.0 Diagram Specifies

The **Agent Lead (Synthesis & Decision Layer)** sits between the Magnets pipeline and the output artifacts. It executes a five-stage workflow:

`SYNTHESIZE → EVALUATE → RECOMMEND → REPORT → HANDOFF PREP`

- **Synthesize**: Correlates score. Distills findings. Cross-ref findings. Detects issues.
- **Evaluate**: Quality score. Test results. Alignment check. Optimizations.
- **Recommend**: Next best decisions. Strategy. Priorities. Presentation format.
- **Report**: Executive summary. Contact package. Findings. Achievements.
- **Handoff Prep**: Directive summary. Ready to share, metadata, next session.

Outputs are: `FINAL REPORT`, `PR PACKAGE`, `NEXT STEPS`, `AUDIT LOG`.

### Current Repo State

`03_AGENTS/agent_lead.md` is a markdown specification of the Agent Lead concept. **No code implementation exists.** The orchestrator (`02_RUNTIME/orchestrator/orchestrator.py`) handles basic mission coordination but does not implement synthesis, evaluation, or structured handoff preparation.

### Ecosystem Findings

| Pattern / Tool | Key Contribution | Link |
|---|---|---|
| **Agent Patterns Catalog — Orchestrator-Workers** | Orchestrator receives task, decides subtasks at runtime, hands to workers, collects results, synthesizes output. Canonical reference. | [agentpatternscatalog.org/patterns/orchestrator-workers](https://agentpatternscatalog.org/patterns/orchestrator-workers) |
| **Zylos "Planner-Generator-Evaluator Harness"** | 3 role-isolated agents: Planner (feature list), Generator (one chunk per fresh context), Evaluator (grades against rubric without seeing Generator's trace). Prevents self-review bias. | [zylos.ai/research/2026-04-26-replayable-agent-runtimes](https://zylos.ai/research/2026-04-26-replayable-agent-runtimes) |
| **NSO (Neuro-Symbolic Orchestrator)** | 8 agents: Oracle, Analyst, Builder, Designer, Janitor, CodeReviewer, Librarian, Scout. 3 workflows: BUILD, DEBUG, REVIEW. TDD mandatory. No self-review. LOG FIRST (evidence before hypothesis). | (internal research) |
| **Digital Applied — 7-role taxonomy** | Researcher, Drafter, Auditor, Reviewer, Deployer, Router, Escalator. Handoffs use structured-output schemas, not prose. Human gates after audit, not after draft. | [dev.to/digitalapplied](https://dev.to/digitalapplied) |
| **Mir Majeed — 10-agent team** | Athina (lead), Scout, Spectra, Pixel, Builder, Auditor, Bugsy, Piper, Nova, Quill. 5 on Opus, 5 on Sonnet. Cost-optimized tiered routing. Lead = synthesis + delegation. | [dev.to/mirmajeed1/i-built-a-10-agent-ai-product-team-in-claude-code](https://dev.to/mirmajeed1/i-built-a-10-agent-ai-product-team-in-claude-code) |
| **Odin Workflow** | 11-phase workflow. Hybrid Orchestration: only orchestrator has MCP access. Task-spawned agents produce artifacts; orchestrator executes MCP ops. Strict tool isolation. | [github.com/Plazmodium/odin-workflow](https://github.com/Plazmodium/odin-workflow) |
| **Mikko Niemelä — Builder + Auditor** | Builder writes plan + code. Auditor writes comments. Neither touches the other's file. Clean separation eliminates self-review contamination. | [mikkoniemela.com/build-with-agents](https://mikkoniemela.com/build-with-agents) |
| **Clawd.bot (thecolab.ai)** | Gateway + agent runtime. Kev (orchestrator), Rex (Codex), Hawk (Opus), Scout (Flash). Delegation through gateway. Orchestrator-only MCP access mirrors Odin pattern. | [thecolab.ai](https://thecolab.ai) |

**Key Insight:** The ecosystem has converged on: (1) a Lead/Orchestrator that plans and delegates but never self-reviews its own artifacts; (2) a strict Auditor role that evaluates without seeing the Generator's reasoning trace; (3) structured JSON schema handoffs (not prose); (4) human gates positioned after audit, not after draft. The v2.0 `SYNTHESIZE → EVALUATE → RECOMMEND → REPORT → HANDOFF PREP` pipeline encodes exactly this pattern.

### Implementation Recommendations

1. **Implement `AgentLead` class** (`02_RUNTIME/orchestrator/agent_lead.py`): stateful Python class that executes the 5-stage pipeline. It reads from the Magnets scoring output (Gold artifacts) and produces the 4 output documents (final report, PR package, next steps, audit log).
2. **Enforce Planner-Generator-Evaluator separation**: never let the same model call that generated a plan also evaluate it. Use separate `Agent(model="opus")` dispatches for the Evaluator stage.
3. **Structured handoff schema**: extend `01_PROTOCOLS/CMP/mission_packet.schema.json` with a `handoff_prep` field: `{ directive_summary, context_snapshot, next_session_goals, audit_log_ref }`.
4. **Wire to session close protocol**: the `12_HANDOFFS/` directory has templates — `AgentLead.handoff_prep()` should auto-populate `AGENT_HANDOFF_TEMPLATE.md` at the end of every session.
5. **MCP-only orchestrator**: following the Odin/Clawd pattern, only the AgentLead should hold MCP client connections; sub-agents receive their inputs/outputs as structured JSON, not raw MCP access.

---

## Gap 4: Agent Workflow Graph (Multi-Agent Roles)

### What the v2.0 Diagram Specifies

An **Agent Workflow Graph** with five named roles arranged in a sequential pipeline:

`Scout Agent (Research/Plan) → Builder Agent (Implement/Build) → Auditor Agent (Review/Validate) → Scribe Agent (Document/Score) → Gate Agent (Quality Gate/Release)`

Runtime Capabilities: State & Memory, Conditional Routing, Native & Batch execution, Parallel / Sequential dispatch, Checkpoint & Resume.

### Current Repo State

`03_AGENTS/AGENT_REGISTRY.md` exists as a registry document. **No Scout, Builder, Auditor, Scribe, or Gate agent classes exist.** The orchestrator (`orchestrator.py`) does basic task coordination but does not implement the graph. The `11_SANDBOX_LAB/agent_adapters/` directory exists (for adapter-level testing) but contains no workflow agents.

### Ecosystem Findings

| System | Roles / Agents | Key Pattern | Link |
|---|---|---|---|
| **Microsoft Magentic-One** | Orchestrator + WebSurfer, FileSurfer, Coder, ComputerTerminal | Orchestrator tracks progress, re-plans on failure | [microsoft.com/en-us/research/articles/magentic-one](https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/) |
| **Ralph (zomars)** | 8 agents polling backlog: Planner, Implementer, Reviewer, Tester, Refactorer, Documenter, Fixer, Merger | Beads-style polling; GitHub/Linear/Jira/Asana integration | [github.com/zomars/ralph](https://github.com/zomars/ralph) |
| **Lisa (tarcisiopgs)** | 8 AI backends: Claude, Gemini, Copilot, Cursor, Goose, Aider, OpenCode, Codex | Kanban → plans issues → implements → pushes → opens PR; CI + review monitoring | [github.com/tarcisiopgs/lisa](https://github.com/tarcisiopgs/lisa) |
| **Pilot (qf-studio)** | 133 features; Haiku (trivial) → Opus 4.6 (standard/complex) | Picks up tickets → plans → implements → quality gates → opens PR | [github.com/qf-studio/pilot](https://github.com/qf-studio/pilot) |
| **CCPM (automazeio)** | PRD → Epic → GitHub Issues → Parallel execution | Git worktrees for isolation; PRD-first decomposition | [github.com/automazeio/ccpm](https://github.com/automazeio/ccpm) |
| **AgentFlow (UrRhb)** | 7-stage Kanban pipeline | Kanban IS the orchestration layer; stateless orchestrator via crontab; conflict-aware scheduling | [github.com/UrRhb/agentflow](https://github.com/UrRhb/agentflow) |
| **AmanPM** | 4-phase: Vision Intake → Product Definition → Planning Decomposition → Autonomous Engineering | TDD by default; ADK-style decomposition | (private) |
| **CueMarshal / Chingono** | 8 agents: Marshal, Ava, Dave, Reese, Tess, Devin, Dot, Linton | Different authority per role; least-privilege deliberate | [clouatre.ca/posts/orchestrating-ai-agents-subagent-architecture](https://clouatre.ca/posts/orchestrating-ai-agents-subagent-architecture) |

**Key Insight:** The ecosystem converges on: (1) issue tracker as state machine (our `bd` covers this); (2) git worktrees for agent isolation (prevents file-level conflicts during parallel work); (3) cost tracking per task; (4) CI/review monitoring loops. The Chromatic v2 workflow graph should be implemented using existing beads (`bd`) as the state machine and git worktrees for execution isolation.

### Implementation Recommendations

1. **Implement agent classes** in `02_RUNTIME/agents/`:
   - `scout_agent.py`: Takes a beads issue → produces research summary + implementation plan JSON
   - `builder_agent.py`: Takes plan JSON + git worktree → produces code artifacts + test results
   - `auditor_agent.py`: Takes artifacts + original plan → produces quality score + review notes (never sees Builder's reasoning trace)
   - `scribe_agent.py`: Takes audit output → produces documentation updates + score record
   - `gate_agent.py`: Takes scribe output + confidence score → routes to auto-proceed, self-heal, or escalate
2. **Use git worktrees** for Builder isolation: each build task gets `git worktree add ../build-<issue-id> -b task/<issue-id>`. Prevents conflicts between parallel builds.
3. **Wire to beads state machine**: Scout claims `bd ready` issue → Builder opens it `in_progress` → Gate closes it with `bd close <id>`. The Kanban board is the orchestration layer.
4. **Cost tracking per task**: each agent dispatched via `Agent()` tool records token cost to the execution log (Gap 6), attributed to the originating beads issue ID.
5. **Model routing per role**: Scout/Auditor/Gate → `claude-sonnet-4-6` (judgment). Builder → `claude-opus-4-8` (maximum capability for implementation). Scribe → `claude-haiku-4-5` (mechanical documentation).

---

## Gap 5: Auto-Intake to Beads

### What the v2.0 Diagram Specifies

**Auto-Intake to Beads**: Magnets auto-detect new goals/requests → create beads issues atomically → assign to pipeline → execution continues. The diagram shows a flow: `Backlog Created → Task Attached → Assigned → Dependencies Ready → In Execution`.

This closes the feedback loop: pipeline outputs (new goals, discovered issues, follow-up work) automatically become beads issues without human intervention.

### Current Repo State

`02_RUNTIME/beads-bridge.ts` (7.7 KB) exists — it bridges the TypeScript runtime to beads operations. **No poller, decomposer, or auto-claimer exists.** Issue creation remains manual (`bd create` commands run by humans or agents with direct shell access).

### Ecosystem Findings

| System | Intake Pattern | Key Technique | Link |
|---|---|---|---|
| **Ralph (zomars)** | Polls GitHub Issues / Linear / Jira / Asana / Plane / Shortcut every 5 min | Atomic task claiming; creates branch from issue number | [github.com/zomars/ralph](https://github.com/zomars/ralph) |
| **AgentFlow (UrRhb)** | Stateless orchestrator reads Kanban state every 15 min via crontab | No daemon, no session dependency; pure state-read dispatch | [github.com/UrRhb/agentflow](https://github.com/UrRhb/agentflow) |
| **Lisa (tarcisiopgs)** | Real-time TUI Kanban; auto-decomposes goals into atomic issues | 'n' = plan, 'r' = process; live state machine | [github.com/tarcisiopgs/lisa](https://github.com/tarcisiopgs/lisa) |
| **Pilot (qf-studio)** | Labels issue "pilot" → claims → creates branch → plans → implements → quality gates → opens PR | Label-driven trigger; zero human steps after labeling | [github.com/qf-studio/pilot](https://github.com/qf-studio/pilot) |
| **CCPM (automazeio)** | PRD creation → Epic planning → Task decomposition → GitHub sync → Parallel execution | Structured PRD as intake format | [github.com/automazeio/ccpm](https://github.com/automazeio/ccpm) |
| **ProjectSync MCP** | 13 tools: `create_issue`, `sprint_management`, `backlog_grooming`, `workflow_automation` | Unified API across Linear/Jira/GitHub/Asana | registry.modelcontextprotocol.io |
| **AmanPM** | Vision Intake → Product Definition → Planning Decomposition → Autonomous Engineering | TDD by default; issue-native from first step | (private) |

**Key Insight:** Auto-intake is a solved pattern: (1) poll a source (external API, pipeline output, or a goal queue); (2) decompose goals into atomic issues using an LLM; (3) claim tasks atomically to prevent double-processing; (4) create branches from issue IDs. The existing `beads-bridge.ts` is the right integration point. A Python-native `auto_intake.py` can call `bd create` → `bd dep add` → `bd update --claim` in sequence.

### Implementation Recommendations

1. **Implement `AutoIntake` pipeline** (`02_RUNTIME/intake/auto_intake.py`):
   - `GoalDecomposer`: takes a high-level goal string → calls LLM → produces list of atomic beads issues with types, priorities, and dependencies
   - `BeadsClaimer`: atomically calls `bd create` + `bd dep add` + `bd update --claim` for each issue
   - `IntakePoller`: async polling loop (configurable interval) that reads from a goal queue (JSONL file or Redis queue)
2. **Goal queue**: `07_LOGS_AND_AUDIT/intake_queue.jsonl` — append-only. Any agent or human can append a goal object `{ id, goal, context, timestamp }`. The poller drains it.
3. **Close-loop feedback**: when the Closure Magnet fires (Gap 1), it should write any newly discovered follow-up goals to `intake_queue.jsonl`. This is how pipeline outputs automatically become new beads issues.
4. **Extend `beads-bridge.ts`**: add `decomposeGoal(goalText: string): BeadsIssue[]` method that wraps the Python `GoalDecomposer` via subprocess or the Chromatic MCP Server.
5. **Label-trigger pattern (from Pilot)**: any beads issue tagged `auto-assign` is immediately claimed by the workflow graph without human intervention.

---

## Gap 6: Decision Log + Audit Trail + Cost Tracking

### What the v2.0 Diagram Specifies

The v2.0 diagram shows **Audit Log** as one of the four primary outputs of the Agent Lead layer. The Decision Magnet captures: confidence score, routing decision, action taken, escalation path, audit trail, lessons learned. The pipeline includes a feedback loop labeled `FEEDBACK LOOP — CONTINUOUS IMPROVEMENT`.

The v1.0 diagram explicitly lists 5 artifact files: `run.log.jsonl`, `tool_calls.jsonl`, `decision_log.jsonl`, `audit_log.jsonl`, `stats_update.jsonl`.

### Current Repo State

`02_RUNTIME/router/observability.py` (2.7 KB) exists as a stub. `07_LOGS_AND_AUDIT/routing/*.jsonl` contains router-level routing decisions only. **No unified execution log.** No OTel export. No cost tracking per mission or per agent task. No decision log. The Decision Magnet class is in the magnet spec but no `decision_magnet.py` exists in `02_RUNTIME/magnets/`.

### Ecosystem Findings

| Tool / Paper | Key Contribution | Link |
|---|---|---|
| **OTel GenAI semconv 1.29+** | Standardized: `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reason`, `gen_ai.tool.call.*`. Cost = tokens × price; append to every span. | [opentelemetry.io/docs/specs/semconv/gen-ai/](https://opentelemetry.io/docs/specs/semconv/gen-ai/) |
| **Zylos — Two-Log Model** | Execution log (deterministic, append-only, idempotency keys): for state rebuild and side-effect deduplication. Observability trace (sampled, indexed, with cost): for diagnostics. Two distinct log types with different retention and access patterns. | [zylos.ai/research/2026-04-29-agent-observability-production-debugging](https://zylos.ai/research/2026-04-29-agent-observability-production-debugging) |
| **Zylos — Cost as correctness signal** | Anomalous cost spikes indicate agent misbehavior. A confused agent loops through tool calls. Budget tracking per task is a behavioral health indicator, not just a billing concern. | [zylos.ai/research/2026-04-29-agent-observability-production-debugging](https://zylos.ai/research/2026-04-29-agent-observability-production-debugging) |
| **AgentTrace (arxiv 2602.10133)** | 3-surface taxonomy captures reasoning chain (cognitive), not just inputs/outputs. Execution log must be complete enough to rebuild state and prevent duplicated side effects. Trace can be sampled, redacted, indexed. | [arxiv.org/pdf/2602.10133](https://arxiv.org/pdf/2602.10133) |
| **Langfuse** | Open-source LLM observability. Cost tracking per trace with per-model pricing. Span-level token attribution. Self-hostable. | [langfuse.com](https://langfuse.com) |
| **Arize Phoenix** | Open-source tracing + evaluation. Span-level cost, latency, token usage. Offline + online evaluators. | [phoenix.arize.com](https://phoenix.arize.com) |
| **Databricks Unity Catalog** | OTel traces → Delta tables → SQL analytics. Join agent traces with business data. PII governance layer. | [databricks.com/blog/observability-any-agent-anywhere-production-ready-tracing-opentelemetry-unity-catalog](https://databricks.com/blog/observability-any-agent-anywhere-production-ready-tracing-opentelemetry-unity-catalog) |
| **REGAL (Adobe)** | Medallion ELT: Bronze (raw telemetry) → Silver (normalized OTel) → Gold (scored artifacts). Version-controlled metrics registry. Deterministic telemetry as first-class design primitive. | [arxiv.org/pdf/2603.03018](https://arxiv.org/pdf/2603.03018) |

**Key Insight:** Two logs, not one. The execution log is deterministic (every call hashed, idempotency keys required, side-effect receipts stored) — this is for recovery and audit. The observability trace is diagnostic (sampled, with annotations and evaluations) — this is for cost tracking and behavioral analysis. Cost is a first-class correctness signal: a cost spike is an alert, not just a billing event.

### Implementation Recommendations

1. **Execution Log** (`07_LOGS_AND_AUDIT/execution/execution.jsonl`): append-only JSONL. Each entry: `{ ts, mission_id, task_id, agent_role, event_type, idempotency_key, model, input_hash, output_hash, tool_name, tool_args_hash, side_effect_receipt, prompt_version, model_version }`. Write this synchronously; never sample.
2. **Observability Trace** (`07_LOGS_AND_AUDIT/traces/`): OTel spans conforming to GenAI semconv 1.29+. Include `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, cost attribution (tokens × per-model rate), latency, evaluation scores. Export via OTLP. Can be sampled and redacted.
3. **Decision Log** (`07_LOGS_AND_AUDIT/decisions/decision_log.jsonl`): one entry per routing decision, confidence gate evaluation, or escalation: `{ ts, mission_id, gate, input_score, band, action, reason, lesson }`. This feeds the Playbook Evolution feedback loop.
4. **Cost tracking**: add `cost_per_token` to `02_RUNTIME/router/contracts.py` → `RouteResponse`. Accumulate per `mission_id`. Alert when cost exceeds budget (`budget.py` already exists — wire it to the observability trace).
5. **Implement `decision_magnet.py`**: the one magnet missing from the spec. It reads from the confidence gate output and writes to the Decision Log.
6. **Self-host Langfuse** for development: add a Docker Compose service in `09_DEPLOYMENT/docker-compose.yml` → configure `observability.py` to export to it.

---

## Gap 7: Confidence Gate v2 + Self-Heal

### What the v2.0 Diagram Specifies

The **Confidence Gate (CMP)** is upgraded in v2.0 with four bands and a self-heal path:

| Score Band | Action |
|---|---|
| 90–100% | **Auto-Proceed** |
| 70–89% | **Proceed** (standard execution) |
| 50–69% | **Caution — Self-Heal** (retry with different approach) |
| 0–49% | **Escalate / Replan** |

The diagram labels this explicitly: "No Human Approval by Design" — the system is designed to operate continuously, validating against quality benchmarks and confidence thresholds. Self-heal is the mechanism that allows the pipeline to recover without human intervention.

The diagram also specifies **Autonomy Levels (L0–L5)**: L0 = fully supervised, L3 = conditional autonomy (human on unusual), L5 = full autonomy (no human approval needed by default).

### Current Repo State

`02_RUNTIME/cmp-bridge/confidence-gate.ts` implements confidence scoring and basic band routing. `02_RUNTIME/router/gate.py` implements privacy, budget, and confidence gates at the router level. Existing confidence bands: 90-100 Very High, 80-89 High, 70-79 Medium-High, 60-69 Medium, 50-59 Low-Medium, 40-49 Low, 0-39 Very Low. **No self-heal logic exists.** No retry, no decomposition, no model fallback in the gate layer. Autonomy Levels (L0–L5) are referenced in the v2 diagram but not implemented.

### Ecosystem Findings

| System | Self-Heal Pattern | Link |
|---|---|---|
| **Lisa (tarcisiopgs)** | Model fallback chain: transient errors (429, quota, timeout) auto-switch to next model in roster | [github.com/tarcisiopgs/lisa](https://github.com/tarcisiopgs/lisa) |
| **Pilot (qf-studio)** | Haiku for trivial → Sonnet for standard → Opus 4.6 for complex. Cost-driven routing with quality gate | [github.com/qf-studio/pilot](https://github.com/qf-studio/pilot) |
| **AgentFlow (UrRhb)** | 3-fix escalation rule: after 2 failed attempts, task escalates to human review queue | [github.com/UrRhb/agentflow](https://github.com/UrRhb/agentflow) |
| **NSO** | LOG FIRST: evidence before hypothesis. 3-fix rule. No retry without new information. | (internal research) |
| **Zylos Research** | Retry with different model/prompt. Decompose into smaller sub-tasks. Inject learned patterns from previous failures. Escalate to human after N retries. Memory store must feed failure patterns back into future prompts. | [zylos.ai/research/2026-04-29-agent-observability-production-debugging](https://zylos.ai/research/2026-04-29-agent-observability-production-debugging) |
| **Braintrust** | Production trace scoring + evaluation → feeds confidence signal. Playground feature re-runs nodes with different models. | [braintrust.dev](https://braintrust.dev) |
| **Coralogix AI Center** | SLM evaluators score every interaction for hallucinations, relevance, tool-selection accuracy in real time | [coralogix.com](https://coralogix.com) |

**Key Insight:** Self-heal is a four-strategy escalation ladder: (1) retry with different prompt/temperature; (2) retry with a more capable model; (3) decompose the task into smaller atomic sub-tasks and re-enter the pipeline; (4) inject learned failure patterns from memory store (`02_RUNTIME/memory/store.py` already has a `learnings` table — this is exactly the right data source). Escalate to human only after N failed attempts. The memory store is the key enabler: it already exists and has the right schema.

### Implementation Recommendations

1. **Implement `SelfHealOrchestrator`** (`02_RUNTIME/orchestrator/self_heal.py`):
   - `attempt_1`: retry with increased temperature + different system prompt
   - `attempt_2`: retry with next model tier up (haiku → sonnet → opus escalation)
   - `attempt_3`: call `GoalDecomposer` (Gap 5) to break task into ≤3 atomic sub-tasks, re-enter pipeline for each
   - `attempt_4`: inject top-3 similar failure patterns from `memory/store.py learnings` table into context, retry
   - `attempt_5`: write to `human_review_queue.jsonl`, mark beads issue `blocked`, notify
2. **Extend `confidence-gate.ts`**: when score falls in 50–69 band, invoke `SelfHealOrchestrator` instead of halting. Return the gate result of the healed attempt.
3. **Implement Autonomy Levels** (`02_RUNTIME/cmp-bridge/autonomy_level.py`): L0 = every action requires approval. L3 = only novel/unusual actions require approval. L5 = full autonomy, gate is advisory. Store current level in `02_RUNTIME/memory/store.py` governance rules table.
4. **Connect memory → self-heal**: `SelfHealOrchestrator.attempt_4()` queries `SELECT * FROM learnings WHERE context_tags OVERLAP ? AND outcome = 'failure' ORDER BY created_at DESC LIMIT 3`. The `store.py` API already supports this pattern.
5. **3-fix escalation rule** (from AgentFlow/NSO): never exceed 3 automated retry attempts before escalating to human. Log every attempt to the execution log (Gap 6) with `{ attempt_n, strategy, score_before, score_after }`.

---

## Recommended Implementation Priority

The following priority ordering is derived from architectural dependency: lower-numbered items unblock higher-numbered items.

### P0 — Foundation (unblocks everything else)

| # | Item | Why First | Est. Effort |
|---|---|---|---|
| 1 | **Two-Log Model** (Gap 6) | All other gaps produce log events; the log infrastructure must exist first | 1–2 days |
| 2 | **Chromatic MCP Server** (Gap 2) | Agent Lead and Workflow Graph agents need MCP tool access; build server first | 2–3 days |
| 3 | **`MagnetOrchestrator` + Intake & Closure magnets** (Gap 1) | Completes the 7-magnet set; unblocks the COLLECT→RECOMMEND pipeline | 1–2 days |

### P1 — Orchestration (builds on P0)

| # | Item | Why | Est. Effort |
|---|---|---|---|
| 4 | **Agent Workflow Graph: Scout + Builder + Auditor** (Gap 4) | Core execution agents; Scout and Auditor are independent-context roles | 3–5 days |
| 5 | **Auto-Intake Pipeline** (Gap 5) | Needs beads-bridge + MCP server (P0); enables closed-loop operation | 1–2 days |
| 6 | **Scribe + Gate agents** (Gap 4) | Depends on Auditor output; Gate depends on Confidence Gate v2 | 1–2 days |

### P2 — Intelligence (builds on P1)

| # | Item | Why | Est. Effort |
|---|---|---|---|
| 7 | **Agent Lead Synthesis Layer** (Gap 3) | Depends on Workflow Graph producing artifacts to synthesize | 2–3 days |
| 8 | **Confidence Gate v2 + Self-Heal** (Gap 7) | Depends on memory store (already built) and execution log (P0) | 2–3 days |
| 9 | **Decision Magnet + Validation Magnet wiring** (Gap 1) | Completes the MagnetOrchestrator pipeline | 1 day |

### P3 — Maturity

| # | Item | Why | Est. Effort |
|---|---|---|---|
| 10 | **Full MCP ecosystem** (Gap 2) — filesystem, git, database, web, terminal servers | Reference implementations exist; wiring is straightforward | 2–3 days |
| 11 | **Autonomy Levels L0–L5** (Gap 7) | Governance feature; builds on all runtime infrastructure | 1–2 days |
| 12 | **Playbook Evolution / Feedback Loop** | Depends on Decision Log (P0) and Agent Lead (P2) being populated | 2–3 days |

---

## Cross-Reference: v2.0 Diagram → Repo → Ecosystem

| Diagram Component | Repo File(s) | Status | Best Ecosystem Reference |
|---|---|---|---|
| Magnets — 7 named magnets | `02_RUNTIME/magnets/*.py` (8 exist) | Partial — Intake & Closure missing, no orchestrator | AgentTrace + OTel GenAI semconv |
| MCP Tool Layer — 8 categories | `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md` | Doc only — no server | FastMCP + MCP official Python SDK |
| Agent Lead — 5-stage pipeline | `03_AGENTS/agent_lead.md` | Doc only — no code | Zylos P-G-E Harness + Digital Applied 7-role |
| Agent Workflow Graph — 5 roles | `03_AGENTS/AGENT_REGISTRY.md` | Doc only — no agents | Ralph + AgentFlow + Pilot |
| Auto-Intake to Beads | `02_RUNTIME/beads-bridge.ts` | Bridge exists, no poller/decomposer | Ralph polling + CCPM decomposer |
| Decision Log / Audit / Cost | `07_LOGS_AND_AUDIT/routing/*.jsonl` | Router only — no unified log | Zylos Two-Log + Langfuse |
| Confidence Gate v2 + Self-Heal | `02_RUNTIME/cmp-bridge/confidence-gate.ts` | Gate exists — no self-heal | Zylos self-heal ladder + NSO 3-fix rule |
| Autonomy Levels L0–L5 | (none) | Not started | AgentFlow 3-fix escalation |
| Playbook Evolution | `04_PLAYBOOKS/*.md` | Static docs only | REGAL Bronze→Silver→Gold pipeline |

---

## References

### Papers & Research

- AgentTrace — 3-surface observability taxonomy: [arxiv.org/pdf/2602.10133](https://arxiv.org/pdf/2602.10133)
- REGAL (Adobe) — Registry-driven telemetry: [arxiv.org/pdf/2603.03018](https://arxiv.org/pdf/2603.03018)
- Zylos — Agent observability & production debugging: [zylos.ai/research/2026-04-29-agent-observability-production-debugging](https://zylos.ai/research/2026-04-29-agent-observability-production-debugging)
- Zylos — Replayable agent runtimes: [zylos.ai/research/2026-04-26-replayable-agent-runtimes](https://zylos.ai/research/2026-04-26-replayable-agent-runtimes)
- Braintrust — Complete guide to agent observability 2026: [braintrust.dev/articles/agent-observability-complete-guide-2026](https://braintrust.dev/articles/agent-observability-complete-guide-2026)
- Laminar — Agent observability: [laminar.sh/article/agent-observability](https://laminar.sh/article/agent-observability)
- Databricks — OTel Unity Catalog tracing: [databricks.com/blog/observability-any-agent-anywhere-production-ready-tracing-opentelemetry-unity-catalog](https://databricks.com/blog/observability-any-agent-anywhere-production-ready-tracing-opentelemetry-unity-catalog)

### MCP Protocol

- Specification (stable 2025-11-05): [modelcontextprotocol.io/specification/2025-11-05](https://modelcontextprotocol.io/specification/2025-11-05)
- Specification (RC 2026-07-28): [modelcontextprotocol.io/specification/2026-07-28-release-candidate](https://modelcontextprotocol.io/specification/2026-07-28-release-candidate)
- Python SDK: [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- Reference Servers: [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- Registry: [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io)

### Agent Workflow Systems

- Agent Patterns Catalog: [agentpatternscatalog.org/patterns/orchestrator-workers](https://agentpatternscatalog.org/patterns/orchestrator-workers)
- Ralph (8-agent polling system): [github.com/zomars/ralph](https://github.com/zomars/ralph)
- Lisa (8-backend Kanban agent): [github.com/tarcisiopgs/lisa](https://github.com/tarcisiopgs/lisa)
- Pilot (ticket → PR automation): [github.com/qf-studio/pilot](https://github.com/qf-studio/pilot)
- AgentFlow (stateless Kanban orchestrator): [github.com/UrRhb/agentflow](https://github.com/UrRhb/agentflow)
- CCPM (PRD → parallel execution): [github.com/automazeio/ccpm](https://github.com/automazeio/ccpm)
- Odin Workflow (11-phase, MCP isolation): [github.com/Plazmodium/odin-workflow](https://github.com/Plazmodium/odin-workflow)

### Multi-Agent Patterns

- Mir Majeed — 10-agent product team: [dev.to/mirmajeed1/i-built-a-10-agent-ai-product-team-in-claude-code](https://dev.to/mirmajeed1/i-built-a-10-agent-ai-product-team-in-claude-code)
- Mikko Niemelä — Builder + Auditor separation: [mikkoniemela.com/build-with-agents](https://mikkoniemela.com/build-with-agents)
- Clawd.bot orchestration: [thecolab.ai](https://thecolab.ai)
- CueMarshal / Chingono — 8-role orchestra: [clouatre.ca/posts/orchestrating-ai-agents-subagent-architecture](https://clouatre.ca/posts/orchestrating-ai-agents-subagent-architecture)

### Observability Tools

- OpenTelemetry GenAI semantic conventions: [opentelemetry.io/docs/specs/semconv/gen-ai/](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- Langfuse (open-source LLM observability): [langfuse.com](https://langfuse.com)
- Arize Phoenix (open-source tracing + eval): [phoenix.arize.com](https://phoenix.arize.com)
- Laminar (OTel-native open-source): [laminar.sh](https://laminar.sh)

---

*Document produced by the v2-gaps-research synthesis agent. Last updated: 2026-05-28. Related: `docs/research/SECOND_THIRD_BRAIN_LANDSCAPE.md`, `01_PROTOCOLS/MAGNETS/MAGNETS_SPEC.md`, `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md`, `03_AGENTS/agent_lead.md`.*
