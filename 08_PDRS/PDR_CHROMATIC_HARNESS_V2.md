# PDR: Chromatic Harness v2 Clean Scaffold

## 1. Executive Summary

Chromatic Harness v2 is a clean-reset autonomous workflow scaffold built around CMP governance, Magnet observability, MCP tool access, runtime orchestration, Beads intake, and a frontend command console.

The goal is to create a provider-agnostic harness where Claude, ChatGPT, Gemini, Codex, local LLMs, ADK agents, LangGraph agents, and future frameworks can operate from the same mission protocol, confidence gates, audit trail, and sandbox testing rules.

## 2. Problem

The current architecture has evolved quickly through ideas, scaffolds, playbooks, agents, repo rules, and automation plans. Continuing to patch the old structure risks:

- duplicated governance
- unclear source of truth
- weak visibility into agent behavior
- uncontrolled tool usage
- hidden state drift
- fragile frontend integration
- unsafe external agent adoption

## 3. Proposed Solution

Create a new scaffold with these separations:

| Layer | Responsibility |
|---|---|
| CMP | Governance, confidence, tool budget, permissions, human gates |
| Magnets | Observability, deterministic telemetry, scoring, anomaly detection |
| MCP | Tool/data access |
| Runtime | LangGraph, ADK, or custom workflow execution |
| Beads | Structured next-action intake |
| Agent Lead | Final synthesis and review |
| Frontend Console | Visibility and rapid action surface |
| Sandbox Lab | Safe external-agent testing |

## 4. Target Pipeline

```text
User Intent / GO
→ CMP Mission Packet
→ Runtime Orchestrator
→ Agent Dispatch
→ MCP Tool Access
→ Magnets Observe Inflection Points
→ Magnet Reports
→ Agent Lead Synthesis
→ Confidence Gate
→ Beads Intake
→ PDR / Handoff / Console Action
→ Next Mission
```

## 5. Magnets Concept

Magnets are deterministic observability probes attached to critical workflow inflection points. They are not independent agents. They collect signal, score risk/confidence, and report findings.

### Initial Magnets

| Magnet | Watches | Output |
|---|---|---|
| Intent Magnet | User prompt, GO command, task trigger | Intent clarity score |
| Scope Magnet | Allowed files, forbidden files, repo boundaries | Scope drift alert |
| Execution Magnet | Tool calls, retries, runtime errors | Execution trace |
| Cost Magnet | Token use, tool calls, runtime budget | Budget risk |
| Confidence Magnet | Evidence quality, reversibility, testability | Confidence delta |
| Validation Magnet | Tests, lint, build, review results | Pass/fail evidence |
| Memory Magnet | Repeated rediscovery, stale context | Memory improvement note |
| Security Magnet | Secrets, risky actions, injection attempts | Stop/escalate signal |

## 6. Frontend Workflow Container

The frontend console should become a command surface for:

- active missions
- agent status
- Magnet event streams
- missed inflection alerts
- Beads queue
- independent reviews
- PDR generation
- quick action dispatch
- confidence/risk visibility

AION/OpenCloud or a similar repo can be evaluated as a frontend base after license, stack, Docker support, auth model, and plugin surface are checked.

## 7. Sandbox Lab

External frameworks such as OpenHuman, Hermes, OpenHands, or future agents must enter through the Sandbox Lab.

### Testing Promotion Ladder

| Stage | Permission | Purpose |
|---|---:|---|
| L0 Dry Run | No tools | Observe reasoning only |
| L1 Read Only | Fake repo reads | Scope discipline |
| L2 Simulated Patch | Patch copy only | Patch quality |
| L3 Sandboxed Execute | Container tests | Reliability |
| L4 Real Repo Draft PR | Branch only | Reviewable integration |
| L5 Trusted Agent | Narrow autonomous work | Proven operation |

## 8. Human Gate Philosophy

Human approval should decrease as confidence, determinism, observability, and reversibility improve.

| Confidence | Action |
|---:|---|
| 90-100 | Auto-proceed |
| 75-89 | Proceed if reversible and bounded |
| 60-74 | Self-heal, replan, or request reviewer |
| 40-59 | Create review package |
| 0-39 | Halt |

## 9. MVP Deliverables

- source-of-truth manifest
- CMP spec and schemas
- Magnets spec and schemas
- Beads spec and schema
- Orchestrator playbook
- GO-mode playbook
- Magnet playbook
- Sandbox Lab scaffold
- Frontend Console placeholder
- Agent handoff templates

## 10. Success Criteria

- A mission can be represented as a CMP packet.
- A workflow can emit Magnet events.
- Magnet reports can generate Beads.
- Agent Lead can produce a final report.
- External agents can be tested in Sandbox Lab without touching real repos.
- Frontend console can display mission, confidence, Magnet events, and Beads.
