# PDR: Sonnet + Kimi Governance Layer

## 0. Metadata

| Field | Value |
|---|---|
| PDR ID | PDR-GOV-SONNET-KIMI-001 |
| Status | Draft |
| Priority | P1 |
| Owner | Human / Chromatic Orchestrator |
| Scope | Current Sonnet + Kimi agent workflow |
| Goal | Prevent tool abuse, drift, duplicate work, and ungoverned autonomy |

---

## 1. Problem

The project currently has Sonnet and Kimi working on tasks, but without a formal governance layer they may:

- overuse tools
- duplicate context gathering
- wander outside scope
- mutate files without confidence scoring
- skip review gates
- fail to log decisions
- continue work without clear stop conditions

This PDR creates a lightweight governance system for the current two-model setup while staying compatible with future swarm expansion.

---

## 2. Decision

Adopt a two-agent governed operating model:

| Role | Model | Primary Function |
|---|---|---|
| Architect / Reviewer | Sonnet | Planning, synthesis, critique, documentation, risk review |
| Builder / Scout | Kimi | Repo inspection, implementation, refactor drafts, long-context execution |

No model may act as an unbounded autonomous agent.

Every task must pass through:

```text
Observe -> Classify -> Score -> Execute -> Validate -> Log -> Queue Next
```

---

## 3. Governance Rules

### 3.1 Confidence Gate

Before execution, the active model must assign:

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

### Action Thresholds

| Confidence | Allowed Action |
|---:|---|
| 90-100 | Execute scoped task |
| 75-89 | Execute with logging |
| 60-74 | Only reversible low-risk changes |
| 40-59 | Plan only |
| 0-39 | Halt |

---

## 4. Tool Budget

| Task Type | Max Tool Calls | Notes |
|---|---:|---|
| Tiny | 3 | One-file change or quick answer |
| Normal | 5 | Standard implementation/review |
| Complex | 10 | Multi-file but bounded |
| Audit | 7 | Read-heavy, no mutation by default |
| Architecture | 8 | Planning only unless approved |

### Stop Conditions

Stop immediately if:

- same file is read more than twice without progress
- task expands beyond assigned scope
- destructive action is needed
- confidence drops below 60
- tests fail twice
- model begins broad repo wandering

---

## 5. Agent Routing

### Use Sonnet For

- architecture decisions
- PDR writing
- system design
- governance review
- ambiguity resolution
- final critique

### Use Kimi For

- repo scanning
- implementation drafts
- refactors
- long-context file digestion
- cheap repeated worker tasks

### Required Review Pattern

```text
Kimi builds -> Sonnet reviews -> Human/Orchestrator approves or reroutes
```

For high-risk work:

```text
Sonnet plans -> Kimi implements -> Sonnet audits -> Human approves
```

---

## 6. Mission Packet Template

Every task sent to Sonnet or Kimi must use this:

```md
# Agent Mission Packet

## Task ID

## Assigned Model
Sonnet / Kimi

## Role
Architect / Builder / Reviewer / Scout

## Objective
[One clear outcome]

## Allowed Files
[List exact paths]

## Forbidden Files
[List protected paths]

## Context
[Relevant project state only]

## Instructions
1. Do the smallest safe next step.
2. Score confidence before action.
3. Stay inside allowed files.
4. Log assumptions.
5. Stop if scope expands.

## Tool Budget
Max tool calls: [number]

## Risk Level
Low / Medium / High / Critical

## Acceptance Criteria
- [criterion]
- [criterion]
- [criterion]

## Stop Conditions
Stop if:
- required context is missing
- destructive action is needed
- tests fail twice
- scope expands
- confidence falls below 60

## Output Required
- Summary
- Files touched
- Confidence score
- Evidence
- Next recommended task
```

---

## 7. Required Logs

After every agent run, append:

```json
{
  "task_id": "",
  "model": "sonnet | kimi",
  "role": "",
  "confidence_score": 0,
  "risk_level": "",
  "tools_used": 0,
  "files_touched": [],
  "result": "",
  "validation": "",
  "next_task": ""
}
```

Recommended file:

```text
docs/governance/AGENT_RUN_LOG.jsonl
```

---

## 8. Files To Add

```text
docs/pdr/PDR-GOV-SONNET-KIMI-001.md
docs/governance/AGENT_MISSION_PACKET_TEMPLATE.md
docs/governance/AGENT_RUN_LOG.jsonl
docs/governance/MODEL_ROUTING_RULES.md
docs/governance/CONFIDENCE_GATE.md
```

---

## 9. Definition of Done

This PDR is complete when:

- Sonnet and Kimi have clear roles
- every task uses a mission packet
- confidence scoring happens before mutation
- tool budgets are enforced
- stop conditions are explicit
- agent runs are logged
- Kimi output is reviewed by Sonnet before promotion

---

## 10. Next Task

Create the governance folder and add the first three control files:

1. `AGENT_MISSION_PACKET_TEMPLATE.md`
2. `CONFIDENCE_GATE.md`
3. `MODEL_ROUTING_RULES.md`
