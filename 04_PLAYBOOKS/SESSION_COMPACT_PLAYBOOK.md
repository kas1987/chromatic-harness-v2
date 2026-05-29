# Session Compact Playbook

Operational companion to [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md).

## When to run

| Trigger | Compact type |
|---------|----------------|
| Phase change (discovery → crank → validation) | Checkpoint |
| ~50% context pressure (many large reads) | Checkpoint |
| ~65% context pressure | **Mandatory** checkpoint |
| Session end / user pause | Full compact + handoff |
| Agent Lead `halt` or `review` decision | Full compact + optional bead |

## Loop

```text
Work → (pressure?) → Snapshot → Externalize → Narrow → Continue OR Hand off
```

## Snapshot commands (copy-paste)

```bash
git branch --show-current
git status --short
git log -1 --oneline
bd ready
pytest tests/ -q
```

## Externalize checklist

- [ ] `bd` issues reflect reality (close / create / update)
- [ ] Code committed with clear message (user-requested or session end)
- [ ] `12_HANDOFFS/sessions/<id>.md` filled from template
- [ ] `.agents/handoffs/latest.json` updated
- [ ] RPI `execution-packet.json` updated if mid-epic

## Orchestrator hook

At mission dispatch, Orchestrator attaches magnets. At mission close:

1. Collect magnet events
2. `POST /missions/{id}/synthesize` (Agent Lead)
3. Persist handoff (`session_compact.write_handoff`)
4. Session completion per AGENTS.md

## Pi / Claude specifics

- **Claude:** Read `AGENTS.md` + `.agents/handoffs/latest.json` at session start
- **Pi:** Same; router gate may append `| CRG N resources` — treat as context budget signal
- **Both:** Never start duplicate work — check beads `in_progress` and git branch first
