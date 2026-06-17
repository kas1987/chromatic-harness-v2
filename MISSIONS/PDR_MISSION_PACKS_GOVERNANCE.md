# PDR: Chromatic Harness Mission Packs, Governance, and Implementation Framework

**Document Type:** Planning and Design Record  
**Status:** Draft for adoption  
**Version:** 0.1.0  
**System:** Chromatic Harness v2  
**Owner:** Human Lead / Harness Architect  
**Primary Users:** Orchestrator, Builder Agents, Auditor Agents, Scribe Agents, Human Reviewers

---

## 1. Executive Summary

Chromatic Harness needs Mission Packs because autonomous or semi-autonomous agents cannot safely operate from loose intent alone. The Mission Pack becomes the contract between human intent, agent action, validation, governance, and repo memory.

This PDR defines a four-level Mission Pack framework:

- **M1 Basic:** Small, low-risk work.
- **M2 Intermediate:** Multi-step work with light planning.
- **M3 Complex:** Cross-system or higher-risk work requiring a standard PDR.
- **M4 Atomic:** Critical, high-risk, architecture/security/production work requiring maximum rigor and sign-off.

The design objective is to keep the Harness fast while stopping the bad pattern: vague task → over-tooling → uncontrolled edits → weak validation → undocumented learning.

---

## 2. Problem Statement

The Harness is increasingly operating across multiple IDEs, agents, subagents, terminals, repos, and automation layers. Without a standard work unit, the system risks:

- Scope creep.
- Duplicate or conflicting missions.
- Agents overusing tools.
- Subagents wandering without clear objectives.
- Missing rollback plans.
- Insufficient validation.
- Weak audit trails.
- Repeated rediscovery of the same repo context.
- Human review fatigue because every task looks equally urgent.

Mission Packs solve this by turning every task into a bounded, reviewable, classifiable unit of work.

---

## 3. Goals

| Goal | Description |
|---|---|
| Right-size process | Apply only the rigor required by mission complexity. |
| Bound agent autonomy | Define allowed files, tools, stop conditions, and validation gates. |
| Improve review quality | Make reviewers evaluate objective, risk, scope, acceptance criteria, and rollback before implementation. |
| Reduce tool waste | Prevent broad, repeated, or irrelevant tool use. |
| Preserve learning | Feed outcomes into decision logs, risk registers, and Harness memory. |
| Enable GO-mode | Allow the Orchestrator to continue work from a queue without requiring full re-prompting. |

---

## 4. Non-Goals

This framework does not attempt to:

- Replace engineering judgment.
- Force full PDRs on tiny tasks.
- Allow agents to bypass human approval for irreversible changes.
- Merge code automatically without validation.
- Treat every idea as ready for implementation.

---

## 5. Mission Classification Model

### 5.1 Level Summary

| Level | Name | Description | PDR Required | Governance |
|---|---|---|---:|---|
| M1 | Basic | Simple, well-defined, low-risk changes | No | Standard |
| M2 | Intermediate | Moderate complexity, some dependencies | Light | Elevated |
| M3 | Complex | Multi-system or high-impact changes | Yes | High |
| M4 | Atomic | Critical, irreversible, production/security/architecture impact | Full | Maximum |

### 5.2 Classification Heuristics

A mission should be escalated when:

- Scope is unclear or expanding.
- Dependencies are complex.
- Impact is broader than expected.
- Rollback is uncertain.
- Security, production, architecture, or data models are involved.
- The agent is not confident in validation.
- Multiple reviewers are required.

### 5.3 Default Classification Rule

Start with the lowest level that safely fits. Escalate immediately when risk, uncertainty, or system impact increases.

---

## 6. Mission Packet Required Fields

| Field | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| Mission ID / Title | Required | Required | Required | Required |
| Objective | Required | Required | Required | Required |
| Background / Context | Optional | Recommended | Required | Required |
| Scope | Required | Required | Required | Required detailed |
| Out of Scope | Optional | Recommended | Required | Required detailed |
| Success Criteria | Required | Required | Required | Required measurable |
| Acceptance Criteria | Required | Required | Required | Required formal |
| Constraints | Optional | Recommended | Required | Required |
| Dependencies | Optional | Recommended | Required | Required mapped |
| Risks and Mitigations | Optional | Recommended | Required | Required detailed |
| Resource / Impact | Optional | Recommended | Required | Required full impact |
| Plan / Approach | Simple steps | Step list | Detailed plan | Comprehensive plan |
| Test Strategy | Basic | Standard | Comprehensive | Exhaustive |
| Rollback / Recovery | N/A | Basic plan | Detailed plan | Full rollback plan |
| Validation and Sign-off | Self / Agent | Agent / Lead | Lead / Architect | Architect / Governance |
| Supporting Documents | None/minimal | Some | Multiple | Full package |
| Reviewers | Optional | 1 reviewer | 2+ reviewers | 3+ reviewers + council |
| Approval Required | No | Yes | Yes | Yes formal |

---

## 7. Governance Levels

| Governance | Trigger | Requirements |
|---|---|---|
| Standard | Low-risk routine work | Minimal oversight, basic logging |
| Elevated | Moderate risk or change tracking required | Reviewer, test summary, decision logging |
| High | High risk or broad impact | Multi-reviewer, pre-implementation validation plan |
| Maximum | Critical or irreversible impact | Formal approval, full audit trail, rollback proof |

---

## 8. Lifecycle

```text
Create → Plan → Review → Execute → Validate → Review Results → Close
```

### 8.1 Create

Define the objective, scope, initial complexity, owner, and requested outcome.

### 8.2 Plan

Choose M1-M4 level. Fill the required template. Identify risks, dependencies, validation method, and rollback needs.

### 8.3 Review

Reviewers confirm that the mission is correctly classified and executable. M3/M4 must not proceed if scope, rollback, or validation are incomplete.

### 8.4 Execute

Implement only the approved mission scope. Agents must obey allowed files, forbidden files, tools, budget, and stop conditions.

### 8.5 Validate

Run the required validation. Evidence must be attached or summarized.

### 8.6 Review Results

Auditor verifies that implementation matches mission intent and acceptance criteria.

### 8.7 Close

Update logs, record lessons, note follow-up tasks, and mark mission closed.

---

## 9. Agent Roles

| Role | Responsibility |
|---|---|
| Orchestrator | Selects or creates the next Mission Pack, classifies complexity, dispatches agents. |
| Scout | Finds only the minimum context required. |
| Builder | Implements scoped changes. |
| Auditor | Reviews diff, evidence, and validation. |
| Scribe | Updates mission logs, decision records, risk registers, and README references. |
| Human Lead | Final authority for approvals and escalation decisions. |

---

## 10. Confidence Gate

Before any agent mutates state, it must score confidence.

| Confidence | Behavior |
|---:|---|
| 90-100 | Execute normally within scope. |
| 75-89 | Execute with normal logging. |
| 60-74 | Execute only if reversible and low risk. |
| 40-59 | Plan only; do not mutate. |
| 0-39 | Halt and escalate. |

### 10.1 Confidence Factors

```text
Confidence =
(Objective Clarity * 0.20) +
(Scope Clarity * 0.20) +
(Evidence Quality * 0.20) +
(Reversibility * 0.10) +
(Tool Fit * 0.10) +
(Risk Awareness * 0.10) +
(Testability * 0.10)
```

---

## 11. Tool Budget

| Task Class | Default Budget | Max Search | Max Read | Max Write | Max Execute |
|---|---:|---:|---:|---:|---:|
| Tiny | 3 | 0 | 1 | 1 | 0 |
| Normal | 5 | 1 | 2 | 1 | 1 |
| Complex | 10 | 2 | 5 | 2 | 1 |
| Architecture | 15 | 3 | 8 | 1 | 0 |
| Incident | 10 | 2 | 5 | 0 | 1 |
| Audit | 7 | 1 | 4 | 0 | 1 |

### 11.1 Tool Abuse Stop Conditions

Halt if:

- Same file is read more than twice without progress.
- Search repeats without new information.
- Tool budget is exceeded.
- Agent explores unrelated repo areas.
- Agent changes files outside scope.
- Agent attempts to infer its own mission instead of using the packet.

---

## 12. Required State Files

Recommended repo-level files:

```text
CHROMATIC_TREES.md
SPRINT_STATE.md
AGENT_HANDOFF_QUEUE.md
DECISION_LOG.md
RISK_REGISTER.md
LEARNINGS_LOG.md
MISSION_LOG.md
```

`CHROMATIC_TREES.md` remains the source of truth for repo structure and placement rules. Mission Packs should reference it rather than duplicating repo structure guidance.

---

## 13. Review Gates

| Gate | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| Intake Complete | Required | Required | Required | Required |
| Complexity Classification | Required | Required | Required | Required |
| Scope Review | Self | Reviewer | Lead | Council |
| Risk Review | Optional | Required | Required | Required formal |
| Rollback Review | N/A | Basic | Required | Required formal |
| Validation Review | Basic | Standard | Comprehensive | Exhaustive |
| Approval | None | Lead | Lead/Architect | Formal sign-off |

---

## 14. Acceptance Criteria

The framework is accepted when:

- M1-M4 templates exist and are usable.
- Mission validation script can identify missing required fields.
- Review and implementation checklists exist.
- Example missions demonstrate right-sizing.
- README gives clear adoption instructions.
- BEAD model defines atomic execution units.
- Agents can use the framework without relying on undocumented assumptions.

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Agents over-document small tasks | M1 explicitly avoids PDR and keeps fields minimal. |
| Agents under-document critical tasks | M3/M4 require PDR, risk, rollback, and validation evidence. |
| Tool overuse | Tool budgets and stop conditions are embedded in packets. |
| False confidence | Confidence factors require evidence quality, testability, and reversibility. |
| Queue drift | Closeout requires next task and state-file updates. |
| Review fatigue | Complexity levels prevent every task from becoming M4. |

---

## 16. Implementation Plan

### Phase 1: Adopt Structure

- Add `/MISSIONS/` framework files.
- Add templates and schema.
- Add example mission packets.

### Phase 2: Wire Agents

- Update Orchestrator to require Mission Packet before dispatch.
- Update Builder/Auditor prompts to obey Mission Packet fields.
- Add `MISSION_LOG.md` and `AGENT_HANDOFF_QUEUE.md` integration.

### Phase 3: Validate

- Run validator on all mission YAML files.
- Add CI check for templates and examples.
- Require M3/M4 manual review before implementation.

### Phase 4: Operationalize GO-mode

- `GO` pulls the next approved task from queue.
- `GO PLAN` creates or improves Mission Pack only.
- `GO BUILD` executes approved mission only.
- `GO AUDIT` reviews completed mission only.
- `GO CLOSE` updates logs and queues next step.

---

## 17. Open Decisions

| Decision | Recommendation |
|---|---|
| Should every PR require a mission? | Yes, at least M1. |
| Should M1 require review? | Optional unless touching shared systems. |
| Should agents create missions automatically? | Yes, but only Orchestrator or Scribe should finalize classification. |
| Should M4 allow autonomous implementation? | No. M4 may be planned by agents, but implementation requires formal approval. |

---

## 18. Final Recommendation

Adopt Mission Packs as the required work contract for Chromatic Harness. Use M1 for speed, M2 for controlled implementation, M3 for serious cross-system changes, and M4 for anything that can cause lasting damage, security exposure, production failure, or architecture drift.

