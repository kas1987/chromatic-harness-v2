# Chromatic Harness Kernel

**Status:** Draft v0.1 — 2026-06-19  
**Tracks:** Command-Center #48  
**Principle:** preserve intent + routing + memory + guardrails while stripping compute, UI, and nonessential features

---

## What is the Kernel?

The Kernel is the minimum viable Harness that remains coherent and safe at any compute tier. Every feature in the Kernel must justify itself by improving at least one of:

- **routing** — gets work to the right model/agent
- **memory** — preserves context across sessions
- **safety** — enforces governance and prevents harm
- **execution** — moves tasks from queue to completion

Anything else is optional or tier-dependent.

```
Chromatic Harness Kernel =
  intent parser
  + task queue
  + command dictionary
  + safety rules
  + memory summary
  + model router
```

---

## Operational Tier Matrix

| Tier | Environment | Models | Capabilities |
|------|-------------|--------|--------------|
| **Nano** | Phone / tiny local model | <3B | Command parsing, summaries, lightweight memory recall, handoff generation |
| **Lite** | Laptop / Ollama | 7–14B local | Queue + routing, small agent loops, SQLite state, optional cloud escalation |
| **Core** | Desktop workstation | 14–72B local | Local models + repo operations, telemetry, session memory |
| **Cloud** | Hosted inference | Full Claude | Heavy reasoning, vector search, multi-tool orchestration |
| **Fleet** | Full Harness | All tiers | Multi-agent orchestration, swarm, governance enforcement, full telemetry |

---

## Mandatory vs Optional Subsystems

### Mandatory (all tiers)
| Subsystem | Purpose |
|-----------|---------|
| Command language parser | Classify and route intent |
| Task queue (JSON/SQLite) | Durable work tracking |
| Model router | Tier-appropriate dispatch |
| Safety rules / governance header check | Prevent unsafe outputs |
| Session memory summary | Compressed context recall |
| Telemetry events (JSONL) | Observability at every tier |

### Optional / Tier-Dependent
| Subsystem | Min Tier |
|-----------|----------|
| Vector semantic memory | Core |
| Multi-agent swarm orchestration | Fleet |
| Review daemon (LLM judgment) | Cloud |
| Repo-scale audit tools | Core |
| Dashboard / statusline | Lite |
| Chromatic Dictionary full index | Lite |
| Workflow engine | Cloud |

---

## Feature-Bloat Audit Criteria

A feature is **bloat** if it:
- Requires >1B parameter model to function
- Adds latency >500ms on a Nano device
- Duplicates an existing subsystem without measurable improvement
- Requires always-on cloud connectivity
- Cannot degrade gracefully when unavailable

Flag candidates with label `bloat-candidate` in beads; escalate to P2 cleanup sprint.

---

## Local-First Execution Rules

1. All queue reads/writes use local SQLite or JSONL — no network required
2. Model router defaults to Tier-0 (Ollama) unless Ollama is down; only then escalates
3. Memory summaries are generated locally before any cloud LLM sees session content
4. Safety rules (governance header, injection guard) run as shell checks — no LLM dependency
5. Telemetry events are written locally first; cloud sync is async and non-blocking
6. Session state (`session-state.json`) is always local; never stored remotely

---

## Cloud Escalation Policy

Escalate to cloud (Tier 3+) only when:
- Ollama is down AND task is not suppressible (checked via `OL_BUMP_MAX_SESSION`)
- Task is explicitly tagged T4 (human-required judgment)
- Local model confidence score < threshold (where implemented)
- Multi-repo synthesis requires cross-context that exceeds local context window

Always emit a structured event when escalating:
```json
{"event": "cloud_escalate", "from_tier": 0, "to_tier": 1, "reason": "ollama-down", "task_id": "..."}
```

---

## Graceful Degradation Behavior

```
Fleet → Core  : disable swarm, keep routing + queue + memory
Core  → Lite  : disable vector search, keep queue + router + telemetry
Lite  → Nano  : disable repo ops, keep command parser + memory summary + safety
Nano  → off   : emit handoff packet, halt cleanly with session state saved
```

At every degradation step:
- Same command language (no syntax changes)
- Same governance rules (safety never degrades)
- Same queue schema (items portable across tiers)
- Same telemetry event format (JSONL, same keys)

---

## Memory Compression Strategy

| Tier | Strategy |
|------|----------|
| Nano | Single compressed summary (<500 tokens), key decisions only |
| Lite | Rolling window summary + bead state snapshot |
| Core | Full session memory + semantic index (local embedding) |
| Cloud | Full memory + vector retrieval + cross-session synthesis |

Compression rules:
- Drop raw tool outputs after summarizing
- Keep bead IDs + status always (tiny, high signal)
- Keep governance decisions always
- Compress code diffs to change summaries after merge
- Never compress safety incidents or audit findings

---

## Mobile-Safe Telemetry / Logging

- All logs are append-only JSONL (no database writes mid-session)
- Log rotation via `harness-log-rotate.sh` keeps files under 200 lines
- No PII in telemetry events (no file contents, no prompts, no user text)
- Events are emitted via `printf` to JSONL — no network calls
- Nano tier emits only: `session_start`, `task_queued`, `task_complete`, `error`

---

## Minimal Command / Runtime Schema

Every tier speaks the same command schema:

```json
{
  "cmd": "<chromatic-command>",
  "intent": "<parsed-intent>",
  "tier": 0,
  "task_id": "<uuid>",
  "context": "<compressed-summary>",
  "safety_checked": true
}
```

Routing decisions are appended:
```json
{
  "route": {"tier": 1, "model": "qwen2.5-7b", "reason": "ollama-down"},
  "dispatched_at": "<iso8601>"
}
```

---

## Follow-Up Items

- [ ] Define Chromatic Command Language taxonomy (see #35, #36)
- [ ] Build command phrase tables per tier (see #35)
- [ ] Define vector architecture for Core/Cloud tiers (see #38)
- [ ] Wire Nano-tier handoff packet format
- [ ] Add bloat-candidate audit to governance drift scanner
