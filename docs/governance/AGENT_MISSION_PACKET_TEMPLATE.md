# Agent Mission Packet Template

> **Machine-readable schema:** `01_PROTOCOLS/MISSION_PACKET_SCHEMA.json` — use for validation and programmatic dispatch.
> This file is the **human-readable companion** for filling out a mission packet manually or reviewing one at a glance.

---

## Task ID
<!-- UUID or m-<slug>, e.g. m-dark-mode-2026-05-28 -->

## Assigned Model
Sonnet / Kimi
<!-- See MODEL_ROUTING_RULES.md for decision criteria -->

## Role
Architect / Builder / Reviewer / Scout

## Objective
<!-- One clear, bounded outcome. If you need more than two sentences, narrow the scope. -->

## Allowed Files
<!-- List exact paths or directories. Must be a subset of the repo. -->

## Forbidden Files
<!-- List protected paths. At minimum: 00_SOURCE_OF_TRUTH/, .git/, secrets, credentials -->

## Context
<!-- Paste only the relevant project state. Do not dump the full codebase — scope to what the model needs. -->

## Instructions
1. Do the smallest safe next step.
2. Score confidence before any mutation (see CONFIDENCE_GATE.md).
3. Stay inside Allowed Files. Any write outside scope is a stop condition.
4. Log assumptions explicitly.
5. Stop and report if scope expands beyond this packet.

## Tool Budget
<!-- From PDR-GOV-SONNET-KIMI-001 §4 Tool Budget table -->
Max tool calls: [3 | 5 | 10 | 7 | 8]
<!-- Tiny=3, Normal=5, Complex=10, Audit=7, Architecture=8 -->

## Risk Level
Low / Medium / High / Critical

## Acceptance Criteria
- [ ] criterion
- [ ] criterion
- [ ] criterion

## Stop Conditions
Stop and report immediately if:
- required context is missing
- a destructive or irreversible action is needed (unless confidence ≥ 90 and reversibility = yes)
- tests fail twice
- scope expands beyond Allowed Files
- confidence falls below 60
- the same file is read more than twice without progress

## Output Required
- **Summary:** what was done
- **Files touched:** list of paths modified
- **Confidence score:** final score with reasoning
- **Evidence:** cite file:line for all claims
- **Next recommended task:** one sentence
