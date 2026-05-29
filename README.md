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

## Agent operations

| Doc | Purpose |
|-----|---------|
| [docs/PRE_SESSION_AND_TOOLS.md](docs/PRE_SESSION_AND_TOOLS.md) | Tools, MCP, and CRG baseline — **regenerate before changing tool exposure** |
| [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md) | Session compaction and handoff protocol |
| [AGENTS.md](AGENTS.md) | Agent rules (beads, push, compact) |

```bash
python scripts/generate_pre_session_inventory.py
```
