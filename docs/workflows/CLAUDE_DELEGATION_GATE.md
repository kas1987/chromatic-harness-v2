# Claude Delegation Gate

Use this gate before delegating tasks to Claude Code during high-throughput windows.

## Goal

Apply the same Harness controls used elsewhere before dispatch:

- Forced pre-session boot refresh
- Governance stack checks
- T-level guardrails
- Complexity classification (C1-C4)
- Router provider recommendation under privacy constraints

## Command

```bash
python scripts/claude_delegate_gate.py --task "<objective>" --bead-id <id> --t-level T2 --privacy-class P1
```

## What the script enforces

1. Runs `python scripts/pre_swarm_gate.py --invoked-by claude`
2. Classifies complexity (`auto` or explicit `C1..C4`)
3. Applies T-level gate (`T4` requires `--allow-t4`)
4. Computes confidence and mutation eligibility
5. Produces router-ranked provider choices
6. Writes delegation artifacts:
- `.agents/handoffs/claude_delegate_packet.json`
- `.agents/handoffs/claude_delegate_prompt.md`

## Correlation contract (required for green observability)

When delegating from automation loops, pass both:

- `--run-id <batch-run-id>`
- `--task-id <per-cycle-task-id>`

For `--invoked-by automation`, both flags are mandatory and the gate fails fast when either is missing.

These IDs are written into delegation packet artifacts and workflow run logs.
`claude_delegation_observability.py` uses them for deterministic pickup correlation before text fallback matching.

Expected result after healthy delegated runs:

- `status=green`
- `pickup_evidence.workflow_matches >= 1`
- `reroute.reason=observed providers align with recommendation`

## Optional direct dispatch

```bash
python scripts/claude_delegate_gate.py --task "<objective>" --t-level T2 --spawn-claude-cli
```

## How to verify Claude picked it up

Run:

```bash
python scripts/claude_delegation_observability.py --write
```

Read `.agents/audits/delegation/latest.json`:

- `pickup_evidence.gate_execute=true` means the gate approved delegation.
- `pickup_evidence.delegate_invoked=true` means delegation packet/prompt was emitted or loop-invoked.
- `pickup_evidence.workflow_matches` / `agent_matches` > 0 means downstream execution logs were correlated.

Status semantics:

- `green`: approved + invoked + correlated downstream telemetry.
- `yellow`: approved + invoked, but correlation is weak (usually telemetry gap).
- `red`: delegation blocked or failed.

## What if Claude reroutes provider/model

Delegation packets include `provider_choices` (recommended routing order).

- `reroute.detected=true` in observability report means observed provider/model drift from recommendation.
- If `reroute.reason` reports telemetry correlation gap, reroute cannot be proven either way.
- Tighten telemetry by increasing canonical coverage for `provider` and `model` in run logs.

## T-level policy in this gate

- `T1-T3`: eligible for normal delegation flow.
- `T4`: blocked unless `--allow-t4` is set.
- `T1/T2` with `C4`: forced `plan_only` output.

## Destructive intent prevention

The gate blocks tasks containing destructive command patterns by default (for example `rm -rf`, `git reset --hard`, `git push --force`, drive format/drop patterns).

- Default: halt with `reason=destructive_intent_blocked`
- Override only with explicit `--allow-destructive`

## Recommended patterns

- Standard delivery: `T2` + `C2/C3` + `P1`.
- Risky integration: `T3` + explicit complexity + verify provider list.
- Secrets/deploy/irreversible: `T4` with explicit approval path.
