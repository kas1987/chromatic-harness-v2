# Beads Object Model

## Purpose

This document defines bead types in Chromatic Harness v2 so agents do not confuse local `bd` issues with runtime dashboard beads, magnet events, learning beads, or canon candidates.

---

## Core Distinction

`bd` is the source of truth for work tracking.

Runtime beads are operational/event objects that may become `bd` issues, learnings, alerts, or canon candidates.

---

## Bead Types

| Type | Source of Truth | Purpose | Durable? |
|---|---|---|---:|
| `bd_issue` | `.beads/dolt/` | Work item / task / bug / follow-up | Yes |
| `runtime_bead` | Console/API runtime store | Execution event or action item | Conditional |
| `magnet_bead` | Magnet event stream | Observation from execution, cost, confidence, anomaly | Conditional |
| `alert_bead` | Runtime + bd if actionable | Risk, failure, policy issue, blocked condition | Yes if actionable |
| `learning_bead` | bd remember / knowledge store | Reusable learning from execution | Yes |
| `handoff_bead` | handoff files + bd link | Session transfer object | Yes |
| `canon_candidate_bead` | knowledge repo / bd | Candidate for promoted Chromatic canon | Yes |

---

## 1. `bd_issue`

A `bd_issue` is the authoritative work-tracking unit.

Examples:

```bash
bd ready
bd show ROUTE-001
bd update ROUTE-001 --claim
bd close ROUTE-001
bd dolt push
```

Rules:

- Use `bd` for all real work tracking.
- Do not replace with markdown TODOs.
- Do not treat `.beads/issues.jsonl` as the wire protocol.
- Sync with `bd dolt push/pull`.

---

## 2. `runtime_bead`

A runtime bead is created during mission execution.

Examples:

- tool call summary
- action item
- intermediate result
- retry event
- confidence shift

Runtime beads may be temporary unless promoted.

Promotion rules:

```text
runtime_bead -> bd_issue if actionable
runtime_bead -> learning_bead if reusable
runtime_bead -> archive if informational only
```

---

## 3. `magnet_bead`

A magnet bead is emitted by observability magnets.

Examples:

- cost anomaly
- confidence drop
- scope creep
- tool loop
- repeated failure
- unexpected success pattern

Promotion rules:

```text
magnet_bead -> alert_bead if urgent
magnet_bead -> learning_bead if reusable
magnet_bead -> ignored/archive if noise
```

---

## 4. `alert_bead`

An alert bead is a risk-bearing event requiring action or review.

Examples:

- privacy gate bypass attempt
- provider cost spike
- tool-use loop
- destructive command request
- missing required handoff

Rules:

- P0/P1 alert beads should become `bd_issue`s.
- P2/P3 alerts may remain runtime-only if resolved during session.

---

## 5. `learning_bead`

A learning bead captures reusable knowledge from a mission.

Examples:

- model performed well/poorly on task type
- MCP profile needs adjustment
- workflow saved time
- failure mode repeated

Rules:

- Use `bd remember` for persistent operational knowledge when available.
- Promote to canon candidate only after evidence and repetition.

---

## 6. `handoff_bead`

A handoff bead is the transfer unit between sessions.

It should include:

- active branch
- active beads
- last completed action
- changed files
- known risks
- next recommended action
- stop conditions

Canonical files:

```text
12_HANDOFFS/sessions/<mission>.md
.agents/handoffs/latest.json
```

---

## 7. `canon_candidate_bead`

A canon candidate bead is a learning or standard proposed for the Chromatic knowledge base.

Examples:

- new routing rule
- new agent antipattern
- new context policy
- provider selection lesson
- successful workflow pattern

Promotion path:

```text
learning_bead
  -> canon_candidate_bead
  -> review
  -> canon registry
  -> source of truth doc
```

---

## Bead Lifecycle

```text
Event
  -> runtime_bead
  -> classify
  -> bd_issue / alert_bead / learning_bead / archive
  -> review
  -> canon_candidate_bead
  -> canon if approved
```

---

## Required Fields

All durable bead-like objects should include:

| Field | Required |
|---|---:|
| id | Yes |
| type | Yes |
| title | Yes |
| source | Yes |
| created_at | Yes |
| priority | Yes |
| status | Yes |
| linked_mission | Conditional |
| linked_bd_issue | Conditional |
| evidence | Conditional |
| promotion_status | Conditional |

Example:

```json
{
  "id": "learn-2026-05-29-001",
  "type": "learning_bead",
  "title": "Remote Ollama should be preferred for C2 coding when desktop is awake",
  "source": "mission:route-provider-selector",
  "priority": "p2",
  "status": "candidate",
  "evidence": ["provider_selector test results", "latency log"],
  "promotion_status": "canon_candidate"
}
```

---

## Dashboard Mapping

The dashboard may display multiple bead types, but it must label them clearly.

Recommended UI labels:

| UI Label | Underlying Type |
|---|---|
| Work | `bd_issue` |
| Runtime | `runtime_bead` |
| Alert | `alert_bead` |
| Learning | `learning_bead` |
| Canon Candidate | `canon_candidate_bead` |

---

## Anti-Patterns

Avoid:

- Treating runtime beads as completed work.
- Treating `.beads/issues.jsonl` as authoritative sync.
- Creating markdown TODOs instead of `bd` issues.
- Promoting one-off observations directly to canon.
- Mixing alert, learning, and work items without type labels.
