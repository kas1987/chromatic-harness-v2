# Per-Task Skill Profiles & Token-Debt Audit (OMH-8)

Bead: `chromatic-harness-v2-w1bf.8` — *Per-task skill hot-swap profiles + token audit*.
Epic: `chromatic-harness-v2-w1bf` — Operating-Model Hardening (OMH).
Governs: `~/.claude/governance/subagent-token-efficiency.md`.

## Problem

`skills-family.ps1 [core|pipeline|trust|toolchain|all]` toggles skills at **family**
granularity. A family is coarse: working a single bead pulls in a whole family's
precontext even when only two or three skills are actually used. That precontext is paid
on **every** turn of the session (it sits in the system prompt), so coarse loading is a
standing token debt, not a one-time cost.

OMH-8 defines **per-task profiles** — a named, minimal skill set per task *type* — for
**hot-swap** at task boundaries, plus a **loaded-skill token-cost audit** so the debt is
measured and minimized per task type rather than assumed.

## Profiles (finer than families)

A profile is the minimal skill set to *start* a task type; more can be hot-swapped in on
demand. Profiles are intentionally small — the default posture is "load less, swap in
when needed", not "load the family in case".

| Profile | Task type | Skills (minimal) | Notes |
|---------|-----------|------------------|-------|
| `author` | bead/epic authoring | `brainstorming`, `plan` | no execution skills |
| `dispatch` | queue dispatch / swarm | `swarm`, `implement` | add `crank` only for hands-free epics |
| `collision` | collision triage | (none beyond core) | uses `bd`/lease CLIs, not skills |
| `review` | PR / diff review | `code-review`, `review`, `verification-before-completion` | |
| `learn` | post-mortem / harvest | `post-mortem`, `harvest`, `harvest-insights` | |
| `route` | model-router work | (core only) | router is code, not a skill |
| `loop` | long-running loops | `loop` | pair with loop-budget guards |
| `promote` | wiki convergence | `harvest`, `status` | see [WIKI_CONVERGENCE_CADENCE.md](../WIKI_CONVERGENCE_CADENCE.md) |
| `implement` | single-issue build | `implement`, `systematic-debugging`, `verification-before-completion` | |
| `debug` | bug hunt | `quick-debug`, `systematic-debugging`, `bug-hunt` | |
| `security` | security review | `security-suite`, `security-review` | |
| `ship` | idea→prod | `ship-idea`, `discovery`, `pre-mortem` | heaviest; load only for full pipeline |

The task-type column maps 1:1 to the operating levels audited in OMH-9
(`docs/playbooks/INDEX.md`): author, dispatch, collision, review, learn, route, loop,
promote.

## Hot-swap protocol

1. At a **task boundary** (claiming a new bead, or `mark_chapter`), resolve the bead's
   type → profile (label/area heuristic, default `implement`).
2. Unload the previous profile's non-overlapping skills; load the new profile's set.
   Families still work as a coarse fallback (`skills-family.ps1`); profiles are the
   fine-grained default.
3. Skills not in the profile remain **swap-in-on-demand** — invoking one loads it for the
   rest of the task without widening the baseline.
4. The profile choice is recorded so the token audit can attribute debt to task type.

## Token-cost audit

Goal: precontext debt is *measured per task type*, not assumed. Inputs:

- `scripts/skill_inventory.py --json` — installed skills, paths, invocation frequency
  (from the chronicle), and staleness/deprecation candidates.
- `scripts/audit_mcp_context.py --profile harness_dev` — MCP precontext tokens.
- `agent_token_audit.py` — per-agent token accounting.

Audit procedure per task type:

1. Snapshot baseline precontext tokens with **no** profile loaded.
2. Load the profile; measure the delta (the profile's standing debt).
3. From the chronicle, compute each profile skill's **invocation rate** for that task
   type. A skill loaded but rarely invoked (low rate, high token cost) is a **demotion
   candidate** → move it to swap-in-on-demand.
4. Emit a per-profile report: `{profile, baseline_tokens, profile_tokens, per_skill: [{skill, tokens, invocations, keep|demote}]}`.

This closes the measure→minimize loop: skills that cost precontext without being used for
a task type are demoted out of that profile, shrinking standing debt without losing
on-demand access.

### Acceptance for "minimized"

A profile is minimized when every skill it loads by default was invoked in ≥ a threshold
fraction of recent tasks of that type (default 25%); skills below threshold are demoted to
swap-in. Re-audit on a cadence (weekly, alongside `skill_inventory.py` deprecation sweep).

## Relationship to families

Profiles do **not** replace `skills-family.ps1`; they refine it. Families remain the
session-level coarse switch (and the fallback when a task type is unknown); profiles are
the per-task default that keeps precontext lean. `all` remains available for exploratory
sessions where the task type is not yet known.

See: [SKILL_DEPRECATION_WORKFLOW.md](SKILL_DEPRECATION_WORKFLOW.md),
`docs/CHROMATIC_OPERATING_MODEL.md` §6.
