# Agent Instructions

> **START HERE:** [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) — mandatory checklist for Claude, Pi, Codex, and all harness agents.

Agents must not infer owner intent from chat context. Execute from explicit artifacts: beads, mission packets, PDRs, playbooks, governance policies, routing config, tests, and handoffs.

**Canonical map:** [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md)  
**Context tiers:** [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](docs/governance/PRE_SESSION_CONTEXT_POLICY.md)  
**Bead types:** [docs/BEADS_OBJECT_MODEL.md](docs/BEADS_OBJECT_MODEL.md)  
**Intake loop:** [docs/INTAKE_QUEUE.md](docs/INTAKE_QUEUE.md) — `scripts/run_intake_cycle.ps1`  
**Automation:** [docs/ops/HARNESS_AUTOMATION_RUNBOOK.md](docs/ops/HARNESS_AUTOMATION_RUNBOOK.md)

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**

```bash
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**

- `scp` — use `-o BatchMode=yes`
- `ssh` — use `-o BatchMode=yes`
- `apt-get` — use `-y`
- `brew` — use `HOMEBREW_NO_AUTO_UPDATE=1`

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

## Session Compact (all harness agents)

**Applies to:** Claude, Pi, Codex, and every runtime operating inside Chromatic Harness v2.

The chat is not the system of record. When context is heavy (~50–65% of effective window) or at phase boundaries, **compact** state into the repo:

| Artifact | Purpose |
|----------|---------|
| `bd` | Open/closed work |
| `12_HANDOFFS/sessions/<mission>.md` | Human-readable handoff |
| `.agents/handoffs/latest.json` | Pointer for next session start |
| `.agents/rpi/execution-packet.json` | In-flight RPI epics |

**Session start:** If `.agents/handoffs/latest.json` exists, read it and the `handoff_path` file before new work.

**Full protocol:** [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md)  
**Playbook:** [04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md](04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md)  
**Template:** [12_HANDOFFS/AGENT_HANDOFF_TEMPLATE.md](12_HANDOFFS/AGENT_HANDOFF_TEMPLATE.md)  
**Pre-session inventory:** [docs/PRE_SESSION_AND_TOOLS.md](docs/PRE_SESSION_AND_TOOLS.md) — regenerate with `python scripts/generate_pre_session_inventory.py` before changing tools/MCP  
**MCP / lean Claude (with or without API):** [docs/CURSOR_CONTEXT_HYGIENE.md](docs/CURSOR_CONTEXT_HYGIENE.md) — `python scripts/audit_mcp_context.py --profile harness_dev`  
**Do not trust / do not do:** [docs/AGENT_ANTIPATTERNS.md](docs/AGENT_ANTIPATTERNS.md) — token burn antipatterns, lite workflows  
**CI guard:** `python scripts/check_agent_operations.py` — fails if mandatory docs are removed

Checkpoint commands:

```bash
git branch --show-current && git status --short && git log -1 --oneline
bd ready
pytest tests/ -q
```

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
7. **Hand off** - Write handoff per [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md) (update `.agents/handoffs/latest.json`)

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->

## After beads: session end

Full checklist (push, `bd dolt push`, handoff): [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) and [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md).
