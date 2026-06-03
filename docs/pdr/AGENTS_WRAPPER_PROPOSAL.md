# Proposed `AGENTS.md` Wrapper

> Replace the current duplicated `AGENTS.md` body with a thinner wrapper like this, unless the generated Beads integration block must remain for tool compatibility.

```md
# Agent Instructions

Start here: [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md)

This repo uses Chromatic Harness v2 operating rules. Agents must not infer owner intent from chat context. Agents execute from explicit artifacts: beads, mission packets, PDRs, playbooks, governance policies, routing config, tests, and handoffs.

## Mandatory Rules

- Use `bd` for all task tracking.
- Do not use TodoWrite, TaskCreate, or markdown TODOs as authoritative work state.
- Read `.agents/handoffs/latest.json` if present.
- Run `bd prime` and `bd ready` before selecting work.
- Check git branch and status before edits.
- Follow [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md).
- Follow [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](docs/governance/PRE_SESSION_CONTEXT_POLICY.md).
- Compact and hand off at phase boundaries or session end.

## Session Completion

Work is not complete until:

1. Issues are updated.
2. Quality gates are run when code changed.
3. Changes are committed when appropriate.
4. `git push` succeeds.
5. `bd dolt push` succeeds when beads changed.
6. Handoff files are updated.

## Build & Test

See project-specific build and test docs.
```
```
