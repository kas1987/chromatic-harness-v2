# Chromatic Dictionary

**Bead:** mc-k5d2j (CC #37)  
**Status:** v1.0  
**Date:** 2026-06-19  
**Artifacts:** `COMMAND_DICTIONARY.md` (this file), `TAXONOMY_SCHEMA.json`, `TELEMETRY_TAGS.md`

---

## Part 1: Command Dictionary

Authoritative definitions for all terms used in CCL and the Chromatic Harness.

### A

**agent** — A Claude Code process executing a task from the dispatch queue. Agents are identified by a hex ID written to `.agents/registry/`. An agent holds exactly one claim at a time.

**agent-dictator** — Governance enforcer in `~/bin/`. Releases stale claims (no heartbeat >600s), enforces C-level caps, and writes enforcement events to `.agents/events/`.

**agent-watch** — Universal agent monitor in `~/bin/`. Reads `.agents/registry/` and presents a live view of claimed tasks, runtimes, and health status.

**Axis D** — Billed API axis. External Claude API calls that consume credit balance. Governed by token telemetry and budget caps.

**Axis P** — Prepaid quota axis. Claude Code CLI calls routed through `native_claude_relay`. Zero marginal cost per token.

### B

**bead** — A unit of work tracked in the bd database. Beads have id, title, status, priority, and labels. The canonical issue tracker for all Chromatic Harness work.

**bd** — Beads CLI (v1.0.5). Commands: `ready`, `show`, `close`, `q`, `assign`, `label`, `remember`, `list`.

**budget guard** — A GO Loop exit condition triggered when remaining session tokens fall below 20% of daily cap.

### C

**CCL** — Chromatic Command Language. See `CHROMATIC_COMMAND_LANGUAGE.md`.

**checkpoint** — A partial progress snapshot written by a long-running agent to `.agents/checkpoints/<task-id>.json`. Enables resumption after interruption.

**claim** — An agent's exclusive lock on a task. Written to `.agents/registry/<agent-id>.json`. Stale claims auto-release after 600s.

**C-level** — Cost-tier classification (C1–C4). Determines routing policy, provider selection, and governance approval requirements.

**context** — The infrastructure environment in use: `laptop`, `laptop_remote`, `desktop`, or `server`. Selects routing table section.

### D

**dispatch** — The act of routing a CCL command to a provider based on C-level and routing table. Dispatch results are logged to `07_LOGS_AND_AUDIT/routing/`.

**dispatch queue** — The `.dispatch/` directory. JSON files written here are picked up by the GO Loop within 30s.

### F

**federation** — The process of syncing governance YAML files from `~/.claude/governance/` to all federation roots defined in `workstream-registry.yaml`. Run by `governance-federate.sh`.

**Featherless** — T1 provider in the router matrix. Serves Kimi-K2 and Hermes-3-70B via REST API. Credentials in `~/.claude/secrets/`.

### G

**GO Loop** — The autonomous bead execution mode. Continuously claims and closes beads without pausing for approval. See `AGENT_GO_LOOP.md`.

**governance** — The set of YAML files, hooks, and checks that enforce policy across the harness. Canonical location: `~/.claude/governance/`.

### H

**harness** — The Chromatic Harness: the full system including the router, relay, bd, governance hooks, telemetry, and agent infrastructure.

**heartbeat** — A periodic write by a long-running agent to its registry file, proving liveness. Required every 60s or the agent is considered stale.

### K

**kernel** — The minimal harness subsystem set. Defined in `HARNESS_KERNEL.md`. Nano tier = kernel only.

### M

**Multica** — Autopilot component that dispatches `multica`-tagged beads on a `*/2` cron schedule.

### N

**native_claude** — The `native_claude_relay` provider. Wraps the Claude Code CLI in an HTTP server so the router can dispatch to Axis P instead of Axis D.

### P

**preflight** — Pre-push governance check run by `cross-repo-preflight.sh`. Blocks push if governance files are missing (in strict mode).

**priority** — Bead urgency: P0 (critical), P1 (high), P2 (medium, default), P3 (low).

### R

**relay** — `native_claude_relay.py`. Localhost HTTP server binding `127.0.0.1:9090`. Translates `/complete` requests into `claude -p` CLI invocations.

**router** — The provider selector. Reads `routing-table.yaml` and returns the first reachable provider for a given context × speed_mode × C-level.

### S

**session branch** — A git branch used instead of pushing directly to `main`/`master`. Pattern: `feat/<slug>`.

**speed mode** — Routing preference: `speed` (lowest latency), `balance` (cost/quality trade-off), `low` (cheapest).

### T

**telemetry** — Token usage data written to `07_LOGS_AND_AUDIT/token_governance/`. Read by governance loop to adjust routing weights.

---

## Part 2: Taxonomy Schema

See `docs/architecture/TAXONOMY_SCHEMA.json` for the machine-readable schema. Summary:

```json
{
  "$schema": "...",
  "command": {
    "verb": "string (READ|WRITE|RUN|CONTROL|GOVERN)",
    "noun": "string",
    "qualifiers": ["string"],
    "flags": {"string": "string"},
    "c_level": "string (C1|C2|C3|C4)",
    "domain": "string (session|routing|governance|telemetry|lifecycle)"
  }
}
```

---

## Part 3: Telemetry Tags

See `docs/architecture/TELEMETRY_TAGS.md` for full list. Key tags:

| Tag | Meaning |
|-----|---------|
| `axis:D` | Billed API call |
| `axis:P` | Prepaid CLI call |
| `c_level:C3` | C3-tier dispatch |
| `provider:native_claude` | Relay provider used |
| `provider:gemini` | Gemini fallback used |
| `routed_by:routing_table` | Routing table selected provider |
| `routed_by:power_t4` | Power-T4 override active |
| `governance:ok` | Preflight passed |
| `governance:skip` | Preflight skipped (no-verify) |
| `governance:blocked` | Preflight blocked push |

---

## Related

- `CHROMATIC_COMMAND_LANGUAGE.md` — grammar and taxonomy
- `CHROMATIC_COMMAND_PHRASES.md` — canonical phrase tables
- `AGENT_CONTROL_LOOP.md` — dispatch and queue protocol
