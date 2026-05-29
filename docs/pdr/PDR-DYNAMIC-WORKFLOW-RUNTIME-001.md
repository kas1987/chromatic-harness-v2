# PDR: Dynamic Workflow Runtime for Chromatic Harness

## 0. Metadata

| Field | Value |
|---|---|
| PDR ID | PDR-DYNAMIC-WORKFLOW-RUNTIME-001 |
| Status | Draft |
| Priority | P1 |
| Owner | Human / Chromatic Orchestrator |
| Scope | Chromatic Harness v2 workflow runtime |
| Current Models | Sonnet + Kimi |
| Goal | Convert GO-mode commands into governed, scored, verifiable dynamic workflows |

---

## 1. Problem

The current harness is capable of generating plans, scaffolds, and agent handoffs, but it lacks a bounded workflow runtime that can safely convert vague commands like `GO` into reliable execution.

Without a runtime, agents may:

- wander through the repo
- overuse tools
- duplicate context gathering
- mutate files without confidence checks
- skip review gates
- lose track of project state
- confuse planning, building, verifying, and logging

The result is motion without controlled progress.

---

## 2. Decision

Implement a bounded dynamic workflow runtime that follows this loop:

```text
Observe -> Plan -> Build Task Graph -> Score -> Dispatch -> Verify -> Log -> Queue Next
```

This gives the harness Claude-style dynamic workflow behavior while keeping execution governed, restartable, and auditable.

---

## 3. Non-Goals

This PDR does not implement:

- unbounded autonomous swarm execution
- automatic production deployment
- secret handling
- destructive repo cleanup
- unlimited parallel agents
- hidden background execution

Dynamic does not mean uncontrolled.

---

## 4. Runtime Architecture

```text
User Command
  -> Orchestrator
  -> Project State Reader
  -> Task Graph Builder
  -> Confidence / Risk Gate
  -> Model Router
  -> Worker Execution
  -> Verifier Gate
  -> Run Logger
  -> Next Queue Update
```

---

## 5. Model Roles

| Role | Model | Responsibility |
|---|---|---|
| Orchestrator | GPT / Human / Harness | Selects next objective and controls runtime |
| Architect | Sonnet | Planning, synthesis, system design, critique |
| Worker | Kimi | Repo inspection, implementation drafts, refactors |
| Verifier | Sonnet or GPT | Reviews result before promotion |
| Scribe | Kimi or cheap model | Updates logs, state, queue, and summaries |

---

## 6. GO Modes

| Command | Meaning | Mutation Allowed? |
|---|---|---|
| `GO` | Pick the next safest unblocked task | Yes, if confidence gate passes |
| `GO DEEP` | Inspect, plan, and decompose | Only if explicitly authorized |
| `GO BUILD` | Implement one scoped task | Yes, inside allowed files |
| `GO AUDIT` | Review current state | No |
| `GO VERIFY` | Validate previous output | No mutation except logs |
| `GO SWARM` | Parallel dispatch | Only after approved task graph |

---

## 7. Confidence Gate

Every task must be scored before execution.

```json
{
  "confidence_score": 0,
  "risk_level": "low | medium | high | critical",
  "scope_clarity": 0,
  "evidence_quality": 0,
  "reversibility": "yes | partial | no",
  "tool_budget_fit": true,
  "decision": "execute | plan_only | halt"
}
```

### Thresholds

| Confidence | Allowed Behavior |
|---:|---|
| 90-100 | Execute scoped task normally |
| 75-89 | Execute with standard logging |
| 60-74 | Reversible low-risk changes only |
| 40-59 | Plan only |
| 0-39 | Halt |

---

## 8. Permission Gate

| Action | Rule |
|---|---|
| Read assigned files | Allowed |
| Edit assigned files | Allowed if confidence >= 75 |
| Edit unassigned files | Halt |
| Delete files | Human approval required |
| Change config/build/deploy | Human approval required |
| Touch secrets/env/auth | Halt |
| Run tests | Allowed |
| Install packages | Human approval required |
| Push/merge/deploy | Human approval required |

---

## 9. Verifier Gate

Before a task is promoted to done, the verifier must check:

- objective completed
- scope respected
- files touched are allowed
- confidence score recorded
- risk level recorded
- validation performed or waived with reason
- output is usable by the next agent
- next action is obvious

---

## 10. Required Files

```text
docs/pdr/PDR-DYNAMIC-WORKFLOW-RUNTIME-001.md
docs/workflows/WORKFLOW_RUNTIME.md
docs/workflows/DYNAMIC_WORKFLOW_SPEC.md
docs/workflows/TASK_GRAPH_SCHEMA.json
docs/workflows/PERMISSION_GATE.md
docs/workflows/VERIFIER_GATE.md
docs/workflows/GO_MODES.md
docs/workflows/WORKFLOW_RUN_LOG.jsonl
```

---

## 11. Definition of Done

- [ ] Runtime loop is documented
- [ ] Task graph schema exists
- [ ] Permission gate exists
- [ ] Verifier gate exists
- [ ] GO modes are defined
- [ ] Sonnet/Kimi routing is documented
- [ ] Workflow run log exists
- [ ] No task executes without confidence/risk scoring
- [ ] Human gates are clear

---

## 12. First Implementation Step

Create the workflow runtime folder and add the control files listed in Section 10.
