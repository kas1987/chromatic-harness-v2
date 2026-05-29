# Agent Onboarding Playbook

**Audience:** Claude, Pi, Codex, Cursor agents, and any future harness runtime.

**Authority:** [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md) — this playbook expands it by persona.

---

## Universal rules (non-negotiable)

1. Read [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md) at session start.
2. Use `bd` for tasks — never TodoWrite or ad-hoc markdown TODO lists.
3. Chat history is not the system of record.
4. Regenerate [pre-session inventory](../docs/PRE_SESSION_AND_TOOLS.md) before changing MCP/plugins/CRG.
5. Session end: test → beads → **push** → [handoff](../12_HANDOFFS/SESSION_COMPACT.md).

---

## Persona: Claude (Cursor / Claude Code)

| When | Action |
|------|--------|
| Session open | `CLAUDE.md` + `AGENTS.md` load automatically — verify handoff JSON |
| Before code | `bd ready`, check branch |
| Context heavy | [SESSION_COMPACT checkpoint](../12_HANDOFFS/SESSION_COMPACT.md) |
| Before MCP change | `python scripts/generate_pre_session_inventory.py` |

---

## Persona: Pi (PreToolUse / router)

| When | Action |
|------|--------|
| Agent dispatch | `gate.py` appends CRG advisory — respect `| CRG BLOCKED` |
| Tool budget | ContextGate runs before privacy/confidence gates |
| Session continuity | Same handoff files as Claude |

Pi does not get a separate governance model — CMP + CRG + beads apply equally.

---

## Persona: Codex / subagents

| When | Action |
|------|--------|
| Task scope | Mission packet boundaries only |
| No MCP unless orchestrator grants | Odin pattern: lead holds MCP |
| Output | Structured JSON handoff, not prose-only |

---

## Persona: Agent Lead

| When | Action |
|------|--------|
| Mission close | `POST /missions/{id}/synthesize` |
| Handoff | Auto-writes `12_HANDOFFS/sessions/` + `latest.json` |
| Beads | Suggests follow-up on halt/replan |

---

## Verification (humans + CI)

```bash
python scripts/check_agent_operations.py
pytest tests/ -q
```

CI runs both on every PR.

---

## Training new contributors

1. Walk through [docs/PRE_SESSION_AND_TOOLS.md](../docs/PRE_SESSION_AND_TOOLS.md)  
2. Run a dry compact: fill [AGENT_HANDOFF_TEMPLATE](../12_HANDOFFS/AGENT_HANDOFF_TEMPLATE.md)  
3. Make a trivial beads issue, close it, push  

---

## Related

- [AGENT_REGISTRY.md](../03_AGENTS/AGENT_REGISTRY.md)
- [GO_MODE_PLAYBOOK.md](GO_MODE_PLAYBOOK.md)
- [ORCHESTRATOR_PLAYBOOK.md](ORCHESTRATOR_PLAYBOOK.md)
