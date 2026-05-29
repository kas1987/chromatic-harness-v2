# Session Compact Protocol

> **Authority:** This document is source-of-truth for context management. All harness agents defer here over chat memory.

## Purpose

Long agent sessions lose detail. Compaction moves durable state out of the transcript into the repo and beads so the next session (or the same agent after refresh) can resume without re-exploring the codebase.

**Rule:** The chat is a pointer layer. Git + beads + handoff files hold facts.

---

## Who must follow this

| Runtime | How it loads this protocol |
|---------|---------------------------|
| **Claude** (Cursor, Claude Code) | `AGENTS.md`, `CLAUDE.md`, and this file |
| **Pi** | Same project instructions + router `gate.py` advisories |
| **Codex / other adapters** | `01_PROTOCOLS` + mission packet `required_outputs` |
| **Agent Lead** | Auto-writes handoff via `session_compact.write_handoff()` |

No harness agent may treat the conversation alone as the system of record.

---

## Context pressure signals

You may not see an exact “65%” meter. Use these proxies:

| Signal | Action |
|--------|--------|
| Many large file reads in one session | Stop broad exploration; use targeted reads |
| Re-explaining the same architecture | Compact now |
| Before phase boundary (discovery → implement → validate) | Mandatory compact checkpoint |
| Before `git commit` or session end | Mandatory full compact |
| User says “hand off”, “pause”, “continue later” | Full compact + handoff file |

### Thresholds

| Level | Behavior |
|-------|----------|
| **&lt; 50%** (early) | Normal work; log decisions in beads as you go |
| **~50–65%** (pressure) | Externalize: update beads, snapshot branch/commit, no new scope |
| **~65–80%** (high) | **Compact checkpoint** (below); finish one atomic task only |
| **&gt; 80%** (critical) | No new scope; full handoff; prefer new session |

---

## Compact checkpoint (~65%)

Run in order. Do not skip steps.

### 1. Freeze snapshot (in memory → then file)

```bash
git branch --show-current
git status --short
git log -1 --oneline
bd ready
pytest tests/ -q    # if code changed
```

### 2. Externalize state

| Artifact | What to write |
|----------|----------------|
| **beads** | `bd close` / `bd update` / `bd create` for all touched work |
| **RPI** | Update `.agents/rpi/execution-packet.json` if in an RPI epic |
| **Chronicle** | Append event to `.agents/chronicle/events.jsonl` |
| **Handoff** | Fill [AGENT_HANDOFF_TEMPLATE.md](AGENT_HANDOFF_TEMPLATE.md) → save as `12_HANDOFFS/sessions/<mission-or-date>.md` |
| **Latest pointer** | Write `.agents/handoffs/latest.json` (see schema below) |

### 3. Narrow behavior

- No full-repo search unless a specific symbol is blocking
- Read line ranges, not whole files
- One verification command, not repeated exploration

### 4. Tell the user (short)

- Branch, last commit, test status
- Open beads (`bd ready`)
- Path to handoff file
- Single recommended next command

---

## Full session end

Follow **AGENTS.md → Session Completion** (quality gates, beads, **push**), then:

1. Complete compact checkpoint (above)
2. Ensure `handoff_prep` fields are populated (Agent Lead) or template filled manually
3. Push to remote — work is not done until `git push` succeeds

---

## Session start (resume)

```bash
bd prime
cat .agents/handoffs/latest.json    # if present
# Read handoff_path from JSON, then:
bd ready
git status
```

**Brownfield rule:** Check `git branch` and `.agents/rpi/execution-packet.json` before starting a new RPI epic on top of in-flight work.

---

## `.agents/handoffs/latest.json` schema

```json
{
  "updated_at": "2026-05-28T12:00:00Z",
  "agent": "claude|pi|codex|other",
  "branch": "session/chromatic-harness-v2-initial",
  "last_commit": "9fd0661 feat: MagnetOrchestrator + Agent Lead",
  "mission_id": "CHR-ABC123",
  "handoff_path": "12_HANDOFFS/sessions/CHR-ABC123.md",
  "beads_ready": ["chromatic-harness-v2-xxx"],
  "next_command": "bd show chromatic-harness-v2-xxx"
}
```

---

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| Rely on chat history for issue IDs | `bd show` / `bd ready` |
| Treat `.beads/issues.jsonl` as source of truth | `bd` commands (Dolt DB) |
| Start new RPI without checking execution packet | Read `.agents/rpi/execution-packet.json` |
| Dump entire tool logs into handoff | Links + one-line outcomes |
| Say “ready to push when you are” | Run `git push` per AGENTS.md |

---

## API / Agent Lead integration

After magnet synthesis:

```http
POST /missions/{mission_id}/synthesize?create_bead=true
```

Agent Lead `handoff_prep` is persisted to `12_HANDOFFS/sessions/` when `session_compact.write_handoff()` runs (orchestrator/API path).

---

## Related

- [AGENT_HANDOFF_TEMPLATE.md](AGENT_HANDOFF_TEMPLATE.md)
- [../04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md](../04_PLAYBOOKS/SESSION_COMPACT_PLAYBOOK.md)
- [../AGENTS.md](../AGENTS.md) — Session Completion
- [../01_PROTOCOLS/CMP/CMP_SPEC.md](../01_PROTOCOLS/CMP/CMP_SPEC.md) — Mission packets
