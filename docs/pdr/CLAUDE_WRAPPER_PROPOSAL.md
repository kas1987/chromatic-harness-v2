# Proposed `CLAUDE.md` Wrapper

> Replace duplicated Claude instructions with this thinner Claude-specific wrapper, unless the generated Beads integration block must remain for tool compatibility.

```md
# Claude Instructions for Chromatic Harness v2

Start here: [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md)

Claude must follow the same Harness v2 operating model as all agents.

## Claude-Specific Rules

- Do not use TodoWrite as authoritative project state. Use `bd`.
- Do not bulk-read old Claude JSONL project logs.
- Use lite workflows by default.
- Audit MCP context before long sessions.
- Respect permission gates and stop conditions.
- Do not run unattended `GO SWARM`.
- Compact session state at 50-65% context pressure or phase boundaries.

## Canonical Flow

Follow:

- [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md)
- [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](docs/governance/PRE_SESSION_CONTEXT_POLICY.md)
- [docs/BEADS_OBJECT_MODEL.md](docs/BEADS_OBJECT_MODEL.md)

## Session End

Update beads, run quality gates, commit/push when appropriate, and write handoff.
```
```
