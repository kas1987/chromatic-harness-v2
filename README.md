# Chromatic Harness v2 PDR Package

This package defines the clean-reset scaffold for Chromatic Harness v2.

Core layers:

- CMP: Chromatic Management Protocol, governance and confidence gates
- Magnets: observability probes at workflow inflection points
- MCP: tool/data access layer
- ADK/LangGraph: runtime and workflow orchestration layer
- Beads: intake/action objects generated from findings
- Agent Lead: synthesis, scoring, final findings, next-step recommendation
- Frontend Console: visibility and rapid workflow action surface
- Sandbox Lab: safe testing layer for OpenHuman, Hermes, OpenHands, or other future agent frameworks

Start with `08_PDRS/PDR_CHROMATIC_HARNESS_V2.md`.

## Agent operations (mandatory)

**All agents (Claude, Pi, Codex):** read [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) first.

| Doc | Purpose |
|-----|---------|
| [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) | **Start here** — session start / change-control / session end |
| [docs/PRE_SESSION_AND_TOOLS.md](docs/PRE_SESSION_AND_TOOLS.md) | Tools, MCP, CRG baseline |
| [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md) | Compaction and handoff |
| [04_PLAYBOOKS/AGENT_ONBOARDING_PLAYBOOK.md](04_PLAYBOOKS/AGENT_ONBOARDING_PLAYBOOK.md) | Per-persona rules (Claude, Pi, Codex) |
| [AGENTS.md](AGENTS.md) | Beads, push, compact |

```bash
python scripts/check_agent_operations.py      # CI — verify docs intact
python scripts/generate_pre_session_inventory.py  # after MCP/tool changes
```
