# PDR: Chromatic Command Prompt System

| Field | Value |
|---|---|
| PDR ID | CHCC-PROMPT-000 |
| Status | Draft / Ready for Scaffold |
| Owner | Human Owner + Orchestrator |
| Applies To | chromatic-harness-v2, Command Center, CMP, Magnets, Beads, Agents, Review Swarms |
| Version | 0.1.0 |

## 1. Executive Summary

Create a reusable command prompt system for the Chromatic Harness Command Center with three interchangeable prompt modes:

1. **Operator Command Prompt** - execution and dispatch.
2. **Auditor Command Prompt** - evidence, review, risk, and deterministic reporting.
3. **Designer Command Prompt** - asset swapping, UI composition, theme and visual prompt generation.

The system lets the user switch the Command Center's behavior and visible asset set without changing the underlying harness architecture.

## 2. Problem

The harness needs multiple command styles. A GO-mode operator prompt should not behave like an audit prompt or a visual design prompt. If these modes are mixed, agents will over-search, over-design, or over-execute at the wrong time.

## 3. Objective

Define a stable prompt-mode layer that sits above CMP, Magnets, Beads, and the Command Center UI.

```text
User Intent
-> Command Prompt Mode
-> CMP Mission Packet
-> Runtime / Agents
-> Magnets Observe
-> Beads Intake
-> Command Center Visual State
```

## 4. Non-Objectives

- Do not replace CMP.
- Do not replace MCP.
- Do not make prompts the source of truth.
- Do not allow designer mode to mutate runtime policy.
- Do not let audit mode execute changes unless explicitly promoted.

## 5. Three Prompt Modes

| Mode | Primary Job | Default Autonomy | Primary UI |
|---|---|---:|---|
| Operator | Move work forward | L3-L4 | Mission Control / Pipeline |
| Auditor | Inspect and score | L0-L2 | Logs / Evidence / Risk |
| Designer | Swap assets and compose visuals | L1-L3 | Theme / Layout / Asset Console |

## 6. Shared Requirements

Every prompt mode must produce:

- intent classification
- scope boundary
- confidence score
- risk level
- expected output
- stop conditions
- next action

## 7. Command Center Integration

The Command Center should expose a mode switcher:

```text
Mode: Operator | Auditor | Designer
Asset Pack: Default Neon | Magnetic Gold | Prism Cosmic | Storm Console
Risk View: Compact | Full | Evidence-first
```

Each mode changes:

- prompt template
- visible panels
- button labels
- allowed actions
- asset pack
- inspector behavior
- review depth

## 8. Acceptance Criteria

- [ ] User can choose one of three command prompt modes.
- [ ] Each mode has a PDR and prompt template.
- [ ] Each mode maps to Command Center panels.
- [ ] Asset pack can be swapped without rewriting components.
- [ ] Prompt modes do not override CMP governance.
- [ ] Auditor mode defaults to non-mutating review.
- [ ] Operator mode still requires confidence scoring.
- [ ] Designer mode outputs structured asset instructions.
