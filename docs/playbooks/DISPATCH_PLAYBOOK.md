# Dispatch Playbook

> Issue #81 / NW-RG-081. Implemented by `build_mission_packet()` /
> `dispatch_allowed()` / `_default_tool_budget()` in `scripts/go_mode.py`.

## Purpose

Standardize agent assignment and the mission-packet contract. **No agent is
dispatched without a complete mission packet.**

## Mission packet — required fields

`build_mission_packet()` produces every one of these (missing inputs get safe
defaults, never silent omission):

| Field | Source / default |
|---|---|
| `task_id` | queue item id (or issue number) |
| `objective` | item objective or title |
| `repo` | `kas1987/chromatic-harness-v2` |
| `allowed_files` | item `allowed_files` (else empty → scope flagged low) |
| `forbidden_files` | item value, default `["secrets", "production credentials"]` |
| `owner_agent` | item `owner_agent` (else `unassigned`) |
| `secondary_agent` | item `secondary_agent` (else `unassigned`) |
| `tool_budget` | by risk band (see below) |
| `risk_level` | item `risk_level`, default `medium` |
| `confidence` | full score + 7 factors + band |
| `acceptance_checks` | item acceptance checks (definition of done) |
| `stop_conditions` | item value, default irreversible/credentials/below-gate |
| `required_output` | item value, default "PR with implementation, tests, evidence" |
| `generated_at_utc` | timestamp |

## Tool budgets (`_default_tool_budget`)

| Risk | max_tool_calls | max_files | max_subagents |
|---|---:|---:|---:|
| low | 40 | 6 | 1 |
| medium | 80 | 12 | 2 |
| high / critical | 120 | 20 | 4 |

A queue item may override with an explicit `tool_budget`.

## Dispatch allowed when (`dispatch_allowed`)

- Confidence **≥ 75**, OR confidence **≥ 60** for a reversible, low/medium-risk action, AND
- scope is clear (allowed files or acceptance checks present), AND
- acceptance checks exist, AND
- stop conditions exist.

Below the gate → the packet is still produced but marked `dispatch_allowed:false`
with a reason; the work stays in `plan_only`/`halt`.

## Example mission packet + queue transition

```jsonc
// GO selects the top unblocked P0, scores it, emits this packet:
{
  "task_id": "chromatic-harness-v2-m52x.2",
  "objective": "Implement hook self-test and validation framework",
  "repo": "kas1987/chromatic-harness-v2",
  "allowed_files": ["scripts/hook_selftest.py", "tests/**"],
  "forbidden_files": ["secrets", "production credentials"],
  "owner_agent": "Sentinel",
  "secondary_agent": "Chainbreaker",
  "tool_budget": {"max_tool_calls": 80, "max_files": 12, "max_subagents": 2},
  "risk_level": "medium",
  "confidence": {"score": 82.0, "band": "execute_logged", "may_mutate": true, "factors": {...}},
  "acceptance_checks": ["Self-test command exists", "CI validates hook integrity", "Dashboard reports hook health"],
  "stop_conditions": ["irreversible mutation", "confidence below gate", "requires credentials"],
  "required_output": "PR with implementation, tests, and evidence log"
}
```

Queue transition: `ready → in_progress` happens when the executor **claims** the
bead (`bd update <id> --claim`); GO-mode does not flip state itself — it records
the dispatch decision and hands off the packet.
