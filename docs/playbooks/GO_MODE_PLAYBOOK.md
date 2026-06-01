# GO Mode Playbook

> Issue #81 / NW-RG-081. Implemented by `scripts/go_mode.py`.
> Companion: [CONFIDENCE_GATE](CONFIDENCE_GATE_PLAYBOOK.md) · [DISPATCH](DISPATCH_PLAYBOOK.md) · [ORCHESTRATOR](ORCHESTRATOR_PLAYBOOK.md)

## Purpose

Define how the harness behaves when the user says `GO`. `GO` is permission to
execute the **single highest-value unblocked queued task** — not permission to
wander.

## Execution loop (deterministic)

```
Observe -> Classify -> Score -> Decide -> Dispatch -> Record
```

`scripts/go_mode.py` runs exactly this loop and emits an auditable decision
record. It performs **no code mutation, no commit, and no merge** — it selects,
scores, and produces a mission packet for a (human or sub-agent) executor.

## Required inputs

- The ready work queue — `bd ready --json` (the harness's Next Work queue), or an
  explicit `--queue-file <path.json>`.
- The active issue / mission packet metadata (acceptance checks, risk, owner).
- The [confidence gate](CONFIDENCE_GATE_PLAYBOOK.md).
- Stop conditions.

## Selection rule (`select_next`)

1. Exclude `done / closed / cancelled / deferred`.
2. Exclude anything with `blocked_by` / `blocked`.
3. Prefer ready over planned.
4. Prefer P0 over P1 over P2.
5. Stable tiebreak by id (deterministic — same queue always yields the same pick).

## Decision rule

1. Score confidence with the 7-factor formula.
2. Map to a band (see CONFIDENCE_GATE).
3. **Refuse dispatch when confidence < 60.** Dispatch is permitted at ≥75
   unconditionally, or ≥60 when the task is reversible and low-risk.

## Required output (the decision record)

Every `GO` run records:

- action taken / decision band
- confidence score + the 7 factor values
- selected task (id, title, priority)
- whether dispatch is allowed, and why
- the generated mission packet
- next recommended task (implicit: re-run `GO` after the executor reports)

Persisted with `--write` to `07_LOGS_AND_AUDIT/go_mode/latest.json` and the
mission packet under `07_LOGS_AND_AUDIT/go_mode/missions/<task>.json`.

## Relationship to GO command variants

`docs/workflows/GO_MODES.md` defines the `GO` / `GO DEEP` / `GO BUILD` / `GO SHIP`
family. This playbook + `go_mode.py` are the deterministic backbone for the
**default `GO`**: pick-next-safest-unblocked. Mutating variants (`GO BUILD`,
`GO SHIP`) hand the mission packet to an executor that owns the actual change;
GO-mode itself never mutates.

## Worked example

`GO` against the live queue selected `chromatic-harness-v2-m52x.2` (Hook
self-test, P0), scored confidence **50 → plan_only**, and **refused dispatch**
(sparse acceptance metadata). A queue item carrying full acceptance checks +
allowed files + stop conditions scores ≥75 and dispatch is permitted. See
[DISPATCH_PLAYBOOK](DISPATCH_PLAYBOOK.md) for the example mission packet.
