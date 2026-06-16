# Delegation Matrix & Subagent Governance — Design

**Date:** 2026-04-30
**Owner:** kas41
**Status:** approved (brainstorm), pending plan
**Prerequisite for:** `2026-04-30-routing-enforcement-design.md` Phase B+ (subagent-driven execution unsafe without this)

## Problem

The routing-enforcement design closes the leak at the *prompt boundary* —
ceiling-enforcer hard-blocks when the session model exceeds the routing
table's recommendation. It does **not** address `Agent` (subagent) spawns:

1. **Subagents inherit the parent's full tool surface** unless the caller
   explicitly restricts them. A `code-reviewer` spawned for a read-only
   audit can call `Bash` and `Edit` because nothing validates that the
   chosen subagent_type matches the task class.
2. **Subagents run on whatever model Claude Code's runtime picks** —
   the same routing leak as the parent session, multiplied. A
   `general-purpose` subagent dispatched for a `lookup`-class task burns
   Sonnet/Opus tokens on grep work.
3. **`SUBAGENT_CONSTITUTION.md` is advisory** — it documents the policy
   but is never validated against the actual `Agent` invocation.
4. **`Skill(skill-merchant)` is a polite gate** — Claude is expected to
   call it before tier-1/2 tools, but nothing enforces.
5. **No telemetry on subagent dispatch** — there's no record of what
   subagent_types are spawned for what call_types, on what models, with
   what tools. The data needed to calibrate is missing.

## Goal

A canonical **delegation matrix** keyed by `(call_type × tier)` that
declares, for each task class:
- which subagent_types are allowed,
- which capability tags (and therefore which tools) are permitted,
- the model floor and ceiling,
- the token budget (advisory — used for post-hoc tracking).

Plus a **PreToolUse enforcer** on the `Agent` tool that validates every
spawn against the matrix and hard-blocks structural violations.

The matrix becomes the foundation for both the existing routing-enforcement
work (the `/delegate` slash command consults it) and any future subagent
dispatch.

## Non-Goals

- **Replace `routing-table.yaml`.** That governs inline (in-session) calls.
  The delegation matrix governs `Agent` spawns. They overlap on `model_tier`
  but address different surfaces. Long-term they may converge; not this spec.
- **Auto-route inline calls through the harness.** Out of scope — handled
  by the routing-enforcement spec.
- **Subagent runtime supervision.** The enforcer fires at `PreToolUse`
  (spawn time) only. Once spawned, the subagent operates within whatever
  tool list it was given; we don't intercept individual tool calls inside
  it.

## Architecture

### Decision granularity

Rows keyed by `<call_type>@<tier>`. Up to ~50 pairs in the full table; the
v1 spec ships with ~30 sensible pairs (skipping nonsense combinations like
`architecture@T1` or `lookup@T4`).

### Capability tags + tool registry

Each row declares `capabilities: [...]` from a tag namespace. A small
registry maps tags to actual tool names. New tools are added to the registry
once instead of being added to every row.

```yaml
# ~/.claude/governance/capability-registry.yaml
capabilities:
  fs:read:    [Read, Glob, Grep]
  fs:write:   [Write, Edit, NotebookEdit]
  shell:read: [Bash]                              # paired with read-only command policy
  shell:exec: [Bash]                              # full shell
  agent:      [Agent]
  web:        [WebSearch, WebFetch]
  mcp:local:  ["mcp__ollama-local__*"]
  mcp:cloud:  ["mcp__claude_ai_*", "mcp__neo4j-graphrag__*"]   # excludes ollama-local
  task:       [TaskCreate, TaskUpdate, TaskGet, TaskList]
```

### Allowed-set binding

Each row lists permitted `subagent_types`. The enforcer validates the
caller's chosen `subagent_type ∈ allowed_set`. Most rows have 1-3 entries.

### Sample matrix slice (v1 — illustrative; full table in implementation)

```yaml
# ~/.claude/governance/delegation-matrix.yaml
version: 1
updated: 2026-04-30
schema_url: "https://internal/governance/delegation-matrix.schema.json"

rows:
  - key: lookup@T1
    subagents: [Explore]
    capabilities: [fs:read, mcp:local]
    model: { floor: ollama_resident, ceiling: haiku_4_5 }
    token_budget: { in: 5000, out: 1000 }
    notes: "Grep / find / file-locating queries. Prefer harness-cli; Explore as in-session fallback."

  - key: trivial_edit@T2
    subagents: [general-purpose]
    capabilities: [fs:read, fs:write]
    model: { floor: haiku_4_5, ceiling: haiku_4_5 }
    token_budget: { in: 8000, out: 2000 }

  - key: single_file_edit@T2
    subagents: [general-purpose, application-agent, infrastructure-agent]
    capabilities: [fs:read, fs:write, shell:exec, task]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 30000, out: 8000 }

  - key: multifile_refactor@T2
    subagents: [general-purpose, application-agent]
    capabilities: [fs:read, fs:write, shell:exec, agent, task]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 80000, out: 20000 }

  - key: feature_implementation@T2
    subagents: [general-purpose, application-agent, infrastructure-agent]
    capabilities: [fs:read, fs:write, shell:exec, agent, task]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 100000, out: 30000 }

  - key: bug_diagnosis@T2
    subagents: [general-purpose, Explore]
    capabilities: [fs:read, shell:exec]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 50000, out: 10000 }

  - key: bug_fix@T2
    subagents: [general-purpose, application-agent]
    capabilities: [fs:read, fs:write, shell:exec]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 40000, out: 10000 }

  - key: code_review@T1
    subagents: [code-reviewer]
    capabilities: [fs:read]                       # read-only by design
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 50000, out: 10000 }

  - key: test_authoring@T2
    subagents: [test-runner, general-purpose]
    capabilities: [fs:read, fs:write, shell:exec]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 40000, out: 10000 }

  - key: documentation@T1
    subagents: [documentation-agent, general-purpose]
    capabilities: [fs:read, fs:write]
    model: { floor: ollama_resident, ceiling: haiku_4_5 }
    token_budget: { in: 8000, out: 4000 }

  - key: orchestration@T2
    subagents: [agent-orchestrator]
    capabilities: [fs:read, agent, task]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 30000, out: 8000 }

  - key: architecture@T3
    subagents: [agent-orchestrator, general-purpose]
    capabilities: [fs:read, fs:write, shell:exec, agent, task]
    model: { floor: opus_4_7, ceiling: opus_4_7 }
    token_budget: { in: 200000, out: 50000 }

  - key: long_context_analysis@T2
    subagents: [general-purpose, knowledge-base-agent]
    capabilities: [fs:read]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 150000, out: 20000 }

  - key: premortem_retro@T2
    subagents: [general-purpose]
    capabilities: [fs:read]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 30000, out: 10000 }

  - key: security_audit@T1
    subagents: [code-reviewer]
    capabilities: [fs:read, shell:read]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 60000, out: 15000 }

  - key: perf_optimization@T2
    subagents: [general-purpose, application-agent]
    capabilities: [fs:read, fs:write, shell:exec]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 50000, out: 12000 }

  - key: narrative_authoring@T1
    subagents: [general-purpose, prompt-engineer]
    capabilities: [fs:read, fs:write]
    model: { floor: sonnet_4_6, ceiling: sonnet_4_6 }
    token_budget: { in: 30000, out: 15000 }

  # T3/T4 overlays — system-wide / irreversible escalations
  - key: multifile_refactor@T3
    subagents: [agent-orchestrator]
    capabilities: [fs:read, fs:write, shell:exec, agent, task]
    model: { floor: opus_4_7, ceiling: opus_4_7 }
    token_budget: { in: 150000, out: 40000 }
    notes: "System-wide refactor. Architecture-grade reasoning required."

  - key: feature_implementation@T3
    subagents: [agent-orchestrator]
    capabilities: [fs:read, fs:write, shell:exec, agent, task]
    model: { floor: opus_4_7, ceiling: opus_4_7 }
    token_budget: { in: 200000, out: 50000 }
```

The full table covers ~30 of the 17×4 = 68 possible pairs. Combinations
not in the table fall through to a `defaults` block:

```yaml
defaults:
  unknown_call_type:    # call_type unrecognized
    subagents: [general-purpose]
    capabilities: [fs:read]
    model: { floor: haiku_4_5, ceiling: sonnet_4_6 }
    token_budget: { in: 20000, out: 5000 }
    notes: "Conservative fallback. Update matrix to add the missing row."
  unknown_tier:
    fall_through_to: T2
```

### Enforcer (PreToolUse hook on `Agent`)

```
Agent({subagent_type: X, prompt: P, ...}) intercepted
  │
  ├─ classify(P) → call_type, tier   (via harness --route-only --json)
  ├─ matrix.lookup(call_type@tier) → row (or defaults)
  ├─ validate:
  │    1. X ∈ row.subagents                           → if not: 🔴 hard-block
  │    2. requested tools ⊆ expand(row.capabilities)  → if not: 🔴 hard-block
  │    3. session model ∈ [row.model.floor, row.model.ceiling+1tier]  → cost violation
  │         delta == 0 or 1 tier:  ⚠ counter
  │         delta >= 2 tier:        🔴 hard-block
  ├─ log to ~/.claude/state/subagent-dispatch.jsonl
  │    {ts, call_type, tier, subagent_type, tools_requested, model, severity, allowed}
  │
  └─ exit 0 (allow) | exit 2 (block with one-line reason)
```

Subagents whose `subagent_type` doesn't restrict tools at the harness level
get a *prompt rewriter*: the enforcer prepends a `[DELEGATION-MATRIX]` block
to the subagent's prompt listing its budget and capability set, so the
subagent sees its own constraints and self-restricts.

### Caller-side helpers

A small Python module `~/.claude/lib/delegation_matrix.py` exposes:
- `lookup(call_type, tier) -> Row` — read the matrix
- `validate_spawn(subagent_type, tools, model, call_type, tier) -> Verdict`
- `expand_capabilities(tags) -> set[str]`

The `/delegate` slash command (from routing-enforcement) and the enforcer
both import from this module.

## Components

| Component | Path | Role |
|---|---|---|
| Matrix YAML | `~/.claude/governance/delegation-matrix.yaml` | Canonical (call_type × tier) → policy table |
| Capability registry | `~/.claude/governance/capability-registry.yaml` | Tag → tool-list map |
| Library | `~/.claude/lib/delegation_matrix.py` | Lookup, validation, capability expansion |
| Enforcer hook | `~/.claude/hooks/agent-spawn-enforcer.py` | PreToolUse on `Agent`. Hard-blocks structural violations, counts cost violations. |
| Telemetry log | `~/.claude/state/subagent-dispatch.jsonl` | Every Agent spawn record. |
| Prompt rewriter | inline in enforcer | Prepends `[DELEGATION-MATRIX]` to subagent prompts. |
| Settings wiring | `~/.claude/settings.json` | PreToolUse entry for `Agent` matcher. |

## Data flow

```
parent: Agent({subagent_type, prompt, ...})
   │
   ▼
PreToolUse [matcher: Agent]
   │
   ▼
agent-spawn-enforcer.py
   │
   ├─▶ harness --route-only --json (classify prompt)
   │       │
   │       └─ if degraded: skip enforcement, log advisory
   │
   ├─▶ delegation_matrix.lookup(call_type@tier)
   │
   ├─▶ validate(subagent_type, tools, model, row)
   │       │
   │       ├─ structural violation     → exit 2 with reason
   │       ├─ 2-tier cost violation    → exit 2 with reason
   │       ├─ 1-tier cost violation    → counter only, allow
   │       └─ compliant                → counter only, allow
   │
   ├─▶ append subagent-dispatch.jsonl
   │
   └─▶ rewrite prompt with [DELEGATION-MATRIX] block (allowed cases only)

(spawn proceeds or is blocked)
```

## Failure modes

- **Matrix YAML missing/malformed.** Library raises; enforcer downgrades to
  warn-only mode (logs but never blocks).
- **Harness classifier degraded.** Same as routing-enforcement: enforcer
  treats classification as `unknown_call_type` and uses the conservative
  defaults block. Never block on degraded classifier.
- **Unknown subagent_type.** If the requested subagent_type isn't anywhere
  in the matrix, enforcer treats it as a structural violation and blocks.
  Adding a new subagent_type requires updating the matrix.
- **Tool name renamed by Claude Code release.** Capability registry update
  is the only change needed; matrix rows are unaffected.

## Testing strategy

- **Unit:** `delegation_matrix.py` round-trips known matrix entries; capability
  expansion is correct; defaults fire when a key is missing.
- **Enforcer unit (with `CCC_STATE_DIR`):**
  - structural-violation case → exit 2
  - 2-tier cost violation → exit 2
  - 1-tier cost violation → exit 0, counter incremented
  - compliant → exit 0, counter incremented
  - degraded harness → exit 0 always
  - missing matrix file → exit 0 always
- **Integration:** spawn 5 synthetic `Agent` calls covering each severity,
  verify telemetry log and exit codes.

## Rollout

1. **Phase 0 — Matrix authored.** Land `delegation-matrix.yaml`,
   `capability-registry.yaml`, `delegation_matrix.py` library + tests.
   No enforcer wired yet.
2. **Phase 1 — Telemetry-only.** Land `agent-spawn-enforcer.py` in
   warn-only mode (`MATRIX_ENFORCE=warn` env). Wire into PreToolUse on
   Agent. Run for 3 days. Review `subagent-dispatch.jsonl` to validate
   matrix accuracy and adjust rows that are too tight or too loose.
3. **Phase 2 — Enforce structural violations.** Flip default to enforce
   structural violations only. Cost-tier still warn-only. Run 3 days.
4. **Phase 3 — Full Intensity-2 enforcement.** Cost-tier 2-tier breaches
   start hard-blocking. Mirrors routing-enforcement Intensity 2 posture.
5. **Phase 4 — Resume routing-enforcement plan.** With matrix in place,
   the routing-enforcement plan's Phase B+ tasks can safely use
   subagent-driven execution.

## Success metrics

- Every `Agent` spawn produces a record in `subagent-dispatch.jsonl`.
- After Phase 1: at least 80% of dispatches resolve to a real matrix row
  (rest fall through to defaults — surface for matrix expansion).
- After Phase 3: structural-violation rate = 0; 2-tier cost violations = 0;
  1-tier cost-violation counter trends downward week over week.
- A spawned subagent's tool calls inside the run are a strict subset of
  the row's capabilities (verified spot-check on telemetry).

## Open questions

- **None blocking.** Two follow-ups for v2:
  - Should the matrix include a per-row `dispatcher_preference` field
    (`prefer: harness-cli` for cheap classes) to bias `/delegate` toward
    Ollama vs. Anthropic without changing call_type? Defer.
  - Should the enforcer's prompt rewriter inject the matrix row as a
    machine-readable block the subagent itself can parse, or as prose?
    Start with prose; switch if subagents drift.
