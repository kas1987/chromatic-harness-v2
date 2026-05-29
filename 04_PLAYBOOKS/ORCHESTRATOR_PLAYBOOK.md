# Orchestrator Playbook

## Purpose

The Orchestrator selects the next bounded task, creates a CMP Mission Packet, dispatches the proper agent/runtime, and ensures Magnets are attached before execution.

## Loop

```text
Observe → Classify → Score → Create Mission Packet → Attach Magnets → Dispatch → Validate → Record → Compact/Handoff → Queue Next
```

At mission close: synthesize magnet events (`POST /missions/{id}/synthesize`), persist handoff per [SESSION_COMPACT_PLAYBOOK.md](SESSION_COMPACT_PLAYBOOK.md).

## Required Inputs

- user intent or GO command
- active project state
- Beads queue
- risk register
- model routing matrix
- CMP policy

## Stop Conditions

- confidence below threshold
- scope unclear
- destructive action required
- forbidden tool required
- security risk detected
- validation fails twice
