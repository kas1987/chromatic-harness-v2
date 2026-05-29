# Dynamic Workflow Specification

## Objective

Provide Claude-style dynamic workflows inside Chromatic Harness without unbounded autonomy.

## Workflow Structure

A dynamic workflow contains:

- objective
- task graph
- model routing
- confidence scores
- permission gates
- verifier gates
- logs
- next action

## Standard Flow

```text
User says GO
Orchestrator reads project state
Orchestrator selects one objective
Task graph is created or updated
Each task receives model, role, files, budget, confidence threshold, and stop condition
Worker executes bounded task
Verifier reviews output
Scribe logs result
Queue is updated
```

## Sequential First Policy

Parallel dispatch is forbidden by default.

The default v2 pattern is:

```text
Sonnet plans -> Kimi builds -> Sonnet verifies -> Scribe logs -> Orchestrator queues next
```

## Parallel Dispatch Rule

Parallel dispatch requires:

- approved task graph
- no overlapping file writes
- explicit ownership
- clear merge order
- verifier assigned
- human approval for high-risk work
