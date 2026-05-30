# Continuous Execution & Bead Review SOP

> **Status:** Enforced
> **Applies to:** Claude, Pi, Codex, Cursor agents — every runtime in Chromatic Harness v2.
> **Checker:** `python scripts/continuous_execution_check.py`
> **Parent doctrine:** [AGENT_OPERATIONS.md](../../AGENT_OPERATIONS.md)

## Why

Work stalls when an agent finishes a task and *waits* for the human to say "go".
In an auto-mode harness that is a defect: the next action is almost always
knowable from beads, the execution packet, or the just-completed work. This SOP
makes **continuous forward progress the default** and **bead review a standing
cadence**, so no agent ever idles on a decision it could make itself.

## The Rule

**After completing any unit of work, immediately do ONE of the following — never stop and wait:**

1. **Proceed** to the next concrete step you already identified, OR
2. **Pull** the next item from `bd ready` (highest priority, unblocked), OR
3. **Escalate** — only if the next action is a T4 gate (force push, hard reset,
   firewall/VPN, system `rm -rf`, production secrets) or genuinely ambiguous with
   no reasonable default.

Stopping to ask "should I continue?" for T1–T3 work is a violation of this SOP.

## Mandatory cadence

| Trigger | Action |
|---------|--------|
| **Every response** | End with **three concrete next steps** and begin executing the first. |
| **Task/bead closed** | Run `bd ready`; claim the next unblocked item or proceed to the identified next step. |
| **Adjacent issue found** | File a bead (do **not** sidetrack); continue current task. |
| **Phase boundary** (discovery→build→validate) | Review open beads for the epic; re-rank; continue. |
| **Session start** | `bd prime` + `bd ready` — pick work from beads, not chat. |
| **Session close** | All discovered work captured as beads; handoff names the next command. |

## Bead review discipline

- **Beads are the single source of truth** for work — never TodoWrite, never markdown TODO lists.
- Review `bd ready` at every task boundary, not just at session start.
- Keep the ready queue **clean**: auto-generated/duplicate beads (e.g. repeated
  closeout SWOT seeds) must be deduped or closed — a noisy queue defeats review.
- Every closed bead records what shipped (`bd update --notes`) before `bd close`.

## What still stops (the only stops)

- **T4 gate** reached (see auto-mode-scope.yaml `tier_4`).
- **Physically blocked** — missing credential, external dependency down, merge
  conflict needing human judgment. Capture the blocker as a bead + handoff and
  continue with any other ready work.
- **Explicit human pause** ("stop", "hold", "wait").

Everything else: proceed.

## Enforcement

- `scripts/continuous_execution_check.py` reports: ready-bead count, ready-queue
  noise (duplicate/auto-gen clusters), and whether the last response recorded
  next steps. Advisory by default; `--strict` exits non-zero if the ready queue
  is non-empty and no next-step record exists.
- Intended wiring: session checkpoint / Stop surface (advisory), and the daily
  harness audit.

## References

- [AGENT_OPERATIONS.md](../../AGENT_OPERATIONS.md) — session lifecycle
- [auto-mode-scope.yaml](../../.agents/governance/auto-mode-scope.yaml) — tier policy
- [GOVERNANCE_EXPANSION_GATE.md](../../GOVERNANCE_EXPANSION_GATE.md) — no new layer without proof
