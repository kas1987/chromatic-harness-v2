# Pre-Session Context Policy

## Purpose

This policy defines what an agent may load automatically at session start and what must remain conditional. The goal is to prevent context bloat while preserving enough state for safe execution.

---

## Core Principle

Pre-session context is not a knowledge dump. It is a boot manifest.

Load only what is needed to orient the agent, select work, and enforce governance.

---

## Context Tiers

| Tier | Name | Auto-load? | Purpose |
|---|---|---:|---|
| P0 | Boot minimum | Yes | Orient the agent safely. |
| P1 | Active work | Conditional | Execute the selected bead/mission. |
| P2 | Governance | Conditional | Apply rules when the task touches governance, routing, tools, MCP, or safety. |
| P3 | Deep architecture | No | Load only when implementing or reviewing those systems. |
| P4 | Archive/history | Never by default | Historical evidence only. |

---

## P0 — Always Load

Load these at every session start:

```text
.agents/handoffs/latest.json
Referenced handoff file if present
bd ready summary
git branch --show-current
git status --short
MCP/context audit summary
```

Recommended commands:

```bash
cat .agents/handoffs/latest.json 2>/dev/null || true
bd ready
git branch --show-current
git status --short
python scripts/session_context_report.py --log --invoked-by harness
python scripts/audit_mcp_context.py --profile harness_dev
```

Do not automatically load full logs, old session files, or bulk JSONL traces.

---

## P1 — Load When Executing Active Work

Load only after selecting a bead/mission:

```text
selected bead details
related issue comments
current RPI execution packet, if present
files explicitly in mission scope
acceptance criteria
relevant tests
```

Do not read the whole repository unless the bead explicitly requires an audit.

---

## P2 — Load When Governance Is Relevant

Load governance docs when the task changes or depends on them:

```text
AGENT_OPERATIONS.md
00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md
docs/governance/PRE_SESSION_CONTEXT_POLICY.md
docs/governance/OPENROUTER_BROKER_POLICY.md
docs/BEADS_OBJECT_MODEL.md
routing configs
MCP profiles
permission gates
```

Triggers:

- Changing tools/MCP/CRG.
- Changing routing/provider logic.
- Changing session compact behavior.
- Changing beads workflow.
- Adding provider keys or adapters.
- Dispatching agents.

---

## P3 — Deep Architecture Docs

Load only when necessary:

```text
DEPLOYMENT_GUIDE.md
Detailed playbooks
Full governance architecture
Full provider inventory
Console/API architecture
Historical design records
```

These are not pre-session defaults.

---

## P4 — Archive and History

Never auto-load:

```text
~/.claude/projects/**/*.jsonl
old traces
old handoffs not referenced by latest.json
archived logs
bulk execution histories
large generated reports
stale brainstorming docs
```

Use targeted search or explicit file references only.

---

## Pre-Session Manifest

Each session should produce or log a compact manifest:

```json
{
  "repo": "chromatic-harness-v2",
  "branch": "main",
  "active_beads": [],
  "handoff_pointer": ".agents/handoffs/latest.json",
  "mcp_profile": "harness_dev",
  "context_tier": "P0",
  "loaded_docs": [],
  "blocked_bulk_sources": ["old_logs", "bulk_jsonl", "archive"],
  "routing_context": {
    "device": "unknown",
    "connectivity": "unknown",
    "speed_mode": "balance"
  }
}
```

---

## MCP Policy

Cursor and similar tools may inject all enabled MCP schemas into every turn. Agents must audit MCP context before long sessions and disable unused MCPs for daily harness development.

Daily harness dev should use a lean MCP profile.

Recommended disabled by default unless needed:

- browser automation MCPs
- email/send MCPs
- vendor/security MCPs
- heavy external service MCPs

---

## Which doc when?

| Question | Read this |
|----------|-----------|
| What commands at session start? | [AGENT_OPERATIONS.md](../../AGENT_OPERATIONS.md) |
| What order does work flow? | [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](../../00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md) |
| What may I auto-load (P0–P4)? | This file |
| What MCPs cost tokens? | [PRE_SESSION_AND_TOOLS.md](../PRE_SESSION_AND_TOOLS.md) + `python scripts/audit_mcp_context.py` |
| What MCPs to disable in Cursor? | [CURSOR_CONTEXT_HYGIENE.md](../CURSOR_CONTEXT_HYGIENE.md) |
| What not to automate? | [AGENT_ANTIPATTERNS.md](../AGENT_ANTIPATTERNS.md) + [ops/HARNESS_AUTOMATION_RUNBOOK.md](../ops/HARNESS_AUTOMATION_RUNBOOK.md) |
| Beads vs magnets / runtime beads? | [BEADS_OBJECT_MODEL.md](../BEADS_OBJECT_MODEL.md) |
| OpenRouter routing rules? | [OPENROUTER_BROKER_POLICY.md](OPENROUTER_BROKER_POLICY.md) |
| Full routing architecture (deep)? | [GOVERNANCE_AND_ROUTING_ARCHITECTURE.md](../../GOVERNANCE_AND_ROUTING_ARCHITECTURE.md) — **P3 tier**; load only for implementation/review |

---

## Stop Conditions

Stop and request review if:

- pre-session context exceeds budget before work starts
- duplicate/conflicting operating instructions are detected
- latest handoff points to a missing file
- active bead references missing files
- MCP audit shows unexpected high-token tool surfaces
- task requires raw archive or bulk logs without scope

---

## Canonical Rule

The agent should begin narrow and expand only with evidence.
