---
name: 2026-05-30-delegation-loop-observability-and-shell-safety
source_ids: [2026-05-30-delegation-loop-observability-and-shell-safety]
source_type: learning
confidence: 0.90
suggested_use: delegation success and pickup correlation are different controls
canon_map: general
status: pending
tags: []
---

## Summary

delegation success and pickup correlation are different controls

## Evidence

# Learning: delegation success and pickup correlation are different controls

## What We Learned

A 10-cycle run can show `claude_delegate.returncode=0` in every cycle while delegation observability stays `yellow` when downstream execution logs do not correlate on `task_id` and provider/model fields.

Observed in this session:
- `cycles_completed=10`
- `total_cycles_with_claude_delegate=10`
- `total_delegate_returncode_0=10`
- `delegation.status=yellow`
- `delegation.reroute.reason=no per-task provider observations matched (telemetry correlation gap)`

## Why It Matters

Long-running agent systems need a two-plane success contract:
1. Control plane success (`gated`, `delegated`, `invoked`)
2. Evidence plane success (`correlated`, `attributed`, `auditable`)

Without correlation, reroute behavior cannot be proven or disproven.

## Operational Standard

Treat delegation as complete only when both are true:
- `pickup_evidence.gate_execute=true` and `pickup_evidence.delegate_invoked=true`
- `workflow_matches > 0` or `agent_matches > 0`

## Source

Artifacts:
- `.agents/audits/bead_hygiene/latest_autoloop_report.json`
- `.agents/audits/delegation/latest.json`
- `.agents/handoffs/claude_delegate_packet.json`

---

# Learning: avoid long one-line PowerShell orchestration for parser-critical runs

## What We Learned

Very long single-line PowerShell commands that chain agent loops and JSON extraction are fragile in real sessions:
- accidental control characters (for example `^U`) can corrupt command start
- quoting collisions between PowerShell and embedded Python produce invalid syntax
- shell path state can intermittently surface `python not recognized` despite successful prior runs

Using a here-string piped to `python -` is materially more reliable for deterministic metrics extraction.

## Why It Matters

Telemetry integrity depends on extraction reliability. If parser snippets fail, operators may falsely conclude loops failed or succeeded.

## Safe Pattern

Use:
- short command for workload execution
- separate here-string Python block for artifact parsing
- explicit per-step exit code emission

## Source

Terminal traces from the same 10-cycle batch and corrected parser run in this session.
