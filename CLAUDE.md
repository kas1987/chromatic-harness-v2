# Claude Instructions for Chromatic Harness v2

> **START HERE:** [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) — mandatory for all harness agents. **Auto-mode** (T1–T3 never blocked; T4 only for force push / hard reset / secrets) lives in global `~/.claude/CLAUDE.md`. Proceed immediately; pick the best path and state the choice.

## Claude-specific rules

- Do not use TodoWrite as authoritative project state — use `bd`.
- Do not bulk-read old Claude JSONL project logs.
- Use lite workflows by default (`.claude/workflows/`; antipatterns: [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md)).
- Run `python scripts/audit_mcp_context.py --profile harness_dev` before long sessions.
- Respect permission gates ([docs/workflows/PERMISSION_GATE.md](docs/workflows/PERMISSION_GATE.md)).
- Do not run unattended `GO SWARM` or chain `/crank`.
- Compact session state at 50–65% context pressure or phase boundaries.
- Delegate tasks through `python scripts/claude_delegate_gate.py ...` (see [docs/workflows/CLAUDE_DELEGATION_GATE.md](docs/workflows/CLAUDE_DELEGATION_GATE.md)).

## Production setup (one-time per machine)

```powershell
powershell -File scripts/claude_harness_production_ready.ps1
```

Validates: project `SessionStart`/`SessionEnd` hooks, lite workflows in `~/.claude/workflows`, global SessionStart slimmed. Re-check: `python scripts/validate_claude_harness.py --machine`.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` for full workflow context.

```bash
bd ready
bd show <id>
bd update <id> --claim
bd close <id>
```

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

Issues live in a local Dolt DB; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md
<!-- END BEADS INTEGRATION -->

## Session end

Full checklist (push, `bd dolt push`, handoff): [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) and [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md).
