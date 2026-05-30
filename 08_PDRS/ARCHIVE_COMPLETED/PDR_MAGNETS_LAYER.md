# PDR: Chromatic Magnets Layer

## Purpose

Create a reusable observability layer that attaches deterministic probes to agent workflow inflection points.

## Non-Goal

Magnets are not autonomous workers. They do not execute tasks. They observe, score, and report.

## Inflection Points

- mission_created
- mission_scored
- agent_dispatched
- tool_called
- file_read
- file_changed
- test_started
- test_completed
- error_detected
- retry_attempted
- confidence_scored
- human_gate_triggered
- bead_created
- workflow_completed

## Magnet Output

Each Magnet produces:

- event_id
- mission_id
- timestamp
- magnet_name
- inflection_point
- observed_signal
- risk_delta
- confidence_delta
- evidence
- recommended_action

## Agent Lead Integration

All Magnet reports are sent to the Agent Lead. The Agent Lead correlates findings, removes duplicates, computes trust, generates Beads, and prepares the final report.
