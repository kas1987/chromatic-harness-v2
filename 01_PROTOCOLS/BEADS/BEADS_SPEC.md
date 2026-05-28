# Beads Spec

## Purpose

Beads are structured action/intake objects created from Magnet findings, Agent Lead reports, user intent, failed validations, review findings, or next-step recommendations.

## Bead Lifecycle

```text
created → triaged → assigned → active → review → done
                      ↘ blocked / parked / failed
```

## Required Fields

- bead_id
- title
- source
- priority
- status
- owner
- objective
- evidence
- confidence
- risk
- definition_of_done
- stop_conditions
