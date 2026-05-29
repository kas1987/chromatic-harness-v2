# Handoffs

Structured session continuity for every agent operating inside Chromatic Harness v2.

| Document | Purpose |
|----------|---------|
| [SESSION_COMPACT.md](SESSION_COMPACT.md) | **Canonical protocol** — when and how to compact context |
| [AGENT_HANDOFF_TEMPLATE.md](AGENT_HANDOFF_TEMPLATE.md) | Fillable template for session end |
| `sessions/` | Per-mission handoff files (written by Agent Lead or agents at compact time) |

**Applies to:** Claude (Cursor, Claude Code, API), Pi, Codex, and any runtime adapter registered in the harness.

**Session start rule:** If `.agents/handoffs/latest.json` exists, read it and the referenced handoff file before taking new work.
