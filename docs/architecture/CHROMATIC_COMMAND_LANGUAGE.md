# Chromatic Command Language (CCL) — Taxonomy Framework v0.1

**Bead:** mc-olxac (CC #36)  
**Status:** Draft v0.1  
**Date:** 2026-06-19

---

## Purpose

The Chromatic Command Language (CCL) is a structured vocabulary for interacting with the Chromatic Harness. It defines:
- The grammar for composing commands
- The taxonomy of command categories
- The C-level classification rules for routing and cost attribution
- Disambiguation rules when commands are ambiguous

CCL is not a programming language — it is a human-facing command vocabulary with machine-readable structure. Any agent or tool that accepts CCL input should validate against this spec.

---

## Grammar

### Command Form

```
<verb> [<noun>] [<qualifier>*] [--<flag> <value>*]
```

Examples:
- `dispatch C3 "summarise repo"` → `verb=dispatch noun=C3 qualifier="summarise repo"`
- `route balance C2` → `verb=route qualifier=balance noun=C2`
- `audit governance --scope federation` → `verb=audit noun=governance flag=scope value=federation`

### Verb Classes

| Verb Class | Examples | Effect |
|------------|----------|--------|
| READ | `show`, `list`, `status`, `get`, `check` | No mutation. Always safe. |
| WRITE | `close`, `label`, `assign`, `remember` | Local state mutation. |
| RUN | `dispatch`, `relay`, `execute`, `go-loop` | Process invocation. |
| CONTROL | `stop`, `pause`, `resume`, `reset` | Lifecycle management. |
| GOVERN | `federate`, `audit`, `rollback` | Governance enforcement. |

### Qualifier Classes

| Qualifier | Role |
|-----------|------|
| C-level (`C1`–`C4`) | Sets cost tier and routing policy |
| Speed mode (`speed`, `balance`, `low`) | Routing preference |
| Context (`laptop`, `server`, `desktop`) | Infrastructure context |
| Scope (`--scope federation`) | Narrows the target |

---

## Taxonomy

### Domain 1: Session Management

Commands that control the working session state. Always C1 unless they spawn external processes.

- `bd ready` — surface next tasks
- `bd close` — finalize a task
- `/compact` — compress context
- `/go-loop` — enter autonomous mode (C2 — spawns processes)

### Domain 2: Model Routing

Commands that select or override the model/provider chain.

- `dispatch C3 "<prompt>"` — route to appropriate C3 provider
- `power-t4.sh on` — unlock T4 for session
- `native_claude_relay start` — start relay bridge

Routing decisions are logged to `07_LOGS_AND_AUDIT/routing/` for governance audit.

### Domain 3: Governance Operations

Commands that enforce or inspect governance state.

- `governance-federate.sh` — sync YAML to all federation roots
- `governance-federate.sh --rollback` — restore prior state
- `cross-repo-preflight.sh` — run preflight checks before push

All GOVERN-class commands require preflight to pass unless `--force` is explicitly specified.

### Domain 4: Telemetry & Audit

Commands that read or write telemetry without invoking models.

- `token_governance_closed_loop.py` — generate governance report
- `portfolio_token_telemetry.py` — cross-repo token ledger
- `agent-watch status` — registry health

### Domain 5: Lifecycle Control

Commands that start, stop, or checkpoint long-running agents.

- `touch ~/.claude/.agents/STOP` — graceful GO Loop exit
- `bd label add <id> blocked` — pause and flag for human
- `agent-dictator release <agent-id>` — release stale claim

---

## Disambiguation Rules

When a command phrase is ambiguous:

1. **Verb class wins over noun class.** `dispatch` is always RUN even if the noun is a READ target.
2. **Explicit C-level overrides inferred C-level.** `dispatch C2 "..."` routes as C2 regardless of content complexity.
3. **`--dry-run` always degrades to C1.** No external API call is made.
4. **Unrecognized verbs default to C3 with human confirmation.** Unknown = potentially expensive; confirm first.

---

## Extension Points

CCL v0.1 is intentionally minimal. Extensions in v0.2 will add:

- `PLUGIN:<domain>` noun prefix for MCP tool dispatch
- `BATCH:<n>` qualifier for fan-out across N agents
- `CHECKPOINT:<id>` qualifier for resumable long-running commands
- Structured CCL JSON schema (see `CHROMATIC_DICTIONARY.md` → `TAXONOMY_SCHEMA.json`)

---

## Related

- `CHROMATIC_COMMAND_PHRASES.md` — canonical phrase tables
- `CHROMATIC_DICTIONARY.md` — term definitions and JSON schema
- `AGENT_CONTROL_LOOP.md` — how CCL commands become queue entries
