# Beads Playbook

## Purpose

Defines how findings, alerts, failures, and next actions become Beads.

## Creation Sources

- Magnet report
- Agent Lead report
- failed validation
- missed inflection point
- user request
- PDR action item
- reviewer finding

## Priority Rules

| Priority | Meaning |
|---|---|
| p0 | safety, destructive risk, data loss, production breakage |
| p1 | core project progress or critical dependency |
| p2 | important improvement |
| p3 | backlog or optional exploration |

## Mission Pack layer

Larger work is organized as **Mission Packets** (M1–M4) under `MISSIONS/`. A
Mission Packet is tracked as a `bd` epic; each **BEAD** (slice) of it is a `bd`
issue. There is no separate markdown bead store — `bd` remains the single source
of task truth. See `MISSIONS/BEADS.md` for the full Mission↔`bd` mapping and
`MISSIONS/playbooks/MISSION_PACKET_PLAYBOOK.md` for the operating loop.
