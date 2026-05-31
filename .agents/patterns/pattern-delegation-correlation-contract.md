---
name: delegation-correlation-contract
type: pattern
confidence: 0.90
source_learnings: [2026-05-30-delegation-correlation-contract]
description: Learning: run_id + task_id contract upgrades delegation observability to green
tags: []
---

# Learning: run_id + task_id contract upgrades delegation observability to green

## What We Learned

Adding `run_id` and `task_id` at delegation emission time and propagating them through autoloop + gate + observability produced deterministic correlation.

Validated in-session:
- `STATUS green`
- `WORKFLOW_MATCHES 1`
- `DELEGATION_IDS bhloop-... chromatic-harness-v2-4n4-delegation-c1`
- `REROUTE_REASON observed providers align with recommendation`

## Why It Matters

This closes the evidence-plane gap where delegation happened but could not be attributed to concrete execution events. Reroute analysis is now evidence-based instead of inferred.

## Implementation Notes

- `scripts/bead_hygiene_autoloop.py` now issues per-run and per-cycle IDs.
- `scripts/claude_delegate_gate.py` accepts `--run-id` and `--task-id`, embeds them in packet artifacts, and appends canonical workflow run-log events.
- `scripts/claude_delegation_observability.py` matches by IDs first, then falls back to bead/task text search.

## Source

Artifacts:
- `.agents/audits/bead_hygiene/latest_autoloop_report.json`
- `.agents/audits/delegation/latest.json`
- `.agents/handoffs/claude_delegate_packet.json`
