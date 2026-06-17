# BEADs ↔ `bd`: Mapping Guide

> **This repo has ONE task tracker: `bd` (beads, Dolt-backed).** The project
> CLAUDE.md mandates it and forbids parallel TODO/markdown task stores. This
> document therefore does **not** define a second bead system — it explains how
> the Mission Pack vocabulary (Missions and BEADs) maps onto `bd`, so the
> operating model stays conceptual while execution state lives in `bd`.

## TL;DR mapping

| Mission Pack concept | Lives in `bd` as | Notes |
|---|---|---|
| **Mission Packet** (M2–M4) | a `bd` **epic** | The YAML packet under `MISSIONS/` is the design record; the epic is the tracked unit. |
| **Mission Packet** (M1) | a single `bd` **issue** | Too small for an epic; one issue is enough. |
| **BEAD** (a slice of a mission) | a `bd` **issue** under the epic | One BEAD = one issue. Use `bd dep` to chain them. |
| BEAD status (Proposed/Ready/Active/Blocked/Review/Accepted/Closed) | `bd` status | See status map below. |
| BEAD priority | `bd` priority (p0–p3) | Per `04_PLAYBOOKS/BEADS_PLAYBOOK.md` priority rules. |

A **BEAD** is still the unit defined here — *Bounded, Executable, Auditable,
Decidable, Sequential* — but it is **recorded and tracked as a `bd` issue**, not
as a committed `BEAD-XXX.md` file. Author the slice once (optionally using
`beads/BEAD_TEMPLATE.md` as a thinking scaffold), then create the `bd` issue.

## Status map

| BEAD status (conceptual) | `bd` status |
|---|---|
| Proposed | `open` (unclaimed) |
| Ready | `open` + in `bd ready` |
| Active | `in_progress` (`bd update <id> --claim`) |
| Blocked | `blocked` |
| Review / Accepted | `in_progress` until verified, then `closed` |
| Closed | `closed` (`bd close <id>`) |

## Workflow

```bash
# 1. Author the Mission Packet YAML under MISSIONS/ (right-sized M1-M4).
# 2. Create the tracking epic for an M2-M4 mission:
bd create "M3-MPACK-ADOPT-001: <title>" -t epic -p 1

# 3. Create one issue per BEAD, linked to the epic and chained by dependency:
bd create "BEAD-001: stage MISSIONS/" -p 1
bd dep add <bead-002-id> --needs <bead-001-id>

# 4. Claim, work, close — bd is the source of truth for state:
bd update <id> --claim
bd close <id>
```

## Why no `BEAD-XXX.md` files

Committing markdown bead files would create a second, drifting task store that
the harness governance (PDR_INDEX reconciliation, `bd ready` boot surface, beads
gates) does not read. Keep the **packet** (design intent) in `MISSIONS/`; keep
the **state** (status, deps, priority, claims) in `bd`. The packet references its
epic id; the epic references its packet path.

## BEAD design rules (unchanged)

1. A BEAD should touch the fewest files possible.
2. A BEAD should have one dominant objective.
3. A failed BEAD should not invalidate the whole mission unless it reveals a
   mission-level flaw.
4. BEADs can be parallelized only if they do not touch the same files/decisions.
5. M4 BEADs require explicit gate checks before execution.

## See also

- `04_PLAYBOOKS/BEADS_PLAYBOOK.md` — repo bead creation sources + priority rules.
- `MISSIONS/playbooks/MISSION_PACKET_PLAYBOOK.md` — the operating loop.
- `MISSIONS/beads/BEAD_TEMPLATE.md` — scaffold for thinking through a slice
  before filing the `bd` issue (not a committed artifact).
