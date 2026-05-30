# Claude Instructions for Chromatic Harness v2

> **START HERE:** [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) — mandatory for Claude, Pi, and all harness agents.

Claude must follow the same Harness v2 operating model as all agents. Do not use chat as the system of record.

**Canonical map:** [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md)  
**Context tiers:** [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](docs/governance/PRE_SESSION_CONTEXT_POLICY.md)  
**Bead types:** [docs/BEADS_OBJECT_MODEL.md](docs/BEADS_OBJECT_MODEL.md)  
**Intake loop:** [docs/INTAKE_QUEUE.md](docs/INTAKE_QUEUE.md)  
**Automation:** [docs/ops/HARNESS_AUTOMATION_RUNBOOK.md](docs/ops/HARNESS_AUTOMATION_RUNBOOK.md)

## Claude-specific rules

- Do not use TodoWrite as authoritative project state — use `bd`.
- Do not bulk-read old Claude JSONL project logs.
- Use lite workflows by default (`.claude/workflows/`; see [docs/AGENT_ANTIPATTERNS.md](docs/AGENT_ANTIPATTERNS.md)).
- Run `python scripts/audit_mcp_context.py --profile harness_dev` before long sessions.
- Respect permission gates and stop conditions ([docs/workflows/PERMISSION_GATE.md](docs/workflows/PERMISSION_GATE.md)).
- Do not run unattended `GO SWARM` or chain `/crank`.
- Compact session state at 50–65% context pressure or phase boundaries.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Compact (Claude, Pi, and all harness agents)

Do not rely on chat memory alone. At ~50–65% context pressure, phase boundaries, or session end, externalize state:

- **beads** (`bd ready`, close/update issues)
- **Handoff file** — `12_HANDOFFS/sessions/<mission>.md` from [AGENT_HANDOFF_TEMPLATE.md](12_HANDOFFS/AGENT_HANDOFF_TEMPLATE.md)
- **Pointer** — `.agents/handoffs/latest.json`

**Session start:** Read `.agents/handoffs/latest.json` if present, then the referenced handoff path.

Canonical protocol: [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md)

**Pre-session inventory:** [docs/PRE_SESSION_AND_TOOLS.md](docs/PRE_SESSION_AND_TOOLS.md) — run `python scripts/generate_pre_session_inventory.py` before changing MCP/tools.  
**MCP / lean context:** [docs/CURSOR_CONTEXT_HYGIENE.md](docs/CURSOR_CONTEXT_HYGIENE.md) — disable heavy MCPs in Cursor; `python scripts/audit_mcp_context.py`  
**Antipatterns (token burn):** [docs/AGENT_ANTIPATTERNS.md](docs/AGENT_ANTIPATTERNS.md) — do not trust CRG for Cursor MCP; use lite `/ship`  
**CI guard:** `python scripts/check_agent_operations.py`

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Per [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md) (`.agents/handoffs/latest.json`)

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->

## After beads: session end

Full checklist: [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md). Include `bd dolt push` when beads data changed.
