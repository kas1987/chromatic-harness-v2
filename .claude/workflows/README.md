# Claude Code Workflows (Harness — lite)

**Default workflows here are token-bounded.** Heavy chains that caused ~1.3M token burns are archived as `*.HEAVY.js.bak`.

## Install

```powershell
powershell -File scripts/sync_claude_workflows.ps1
```

## Commands

| Command | What it does | Est. tokens |
|---------|--------------|-------------|
| `/ship [feature]` | Discovery + plan → beads; **no crank** | ~50–150k |
| `/close-issue <id>` | Implement one bead → pytest → push | ~30–80k |
| `/qa` | `pytest` + `ruff` summary only | ~10–30k |
| `/hotfix [bug]` | bug-hunt → minimal patch → pytest → push | ~40–100k |
| `/go [mode]` | `workflow_go.py` → one bead → verify | ~30–80k |

## Rules

1. Workflows pass **bead IDs and file paths** — not full prior agent transcripts.
2. **Never** restore `*.HEAVY.js.bak` without explicit human approval.
3. Read [docs/AGENT_ANTIPATTERNS.md](../../docs/AGENT_ANTIPATTERNS.md) before adding new workflows.

## Do not use (archived)

- `ship.HEAVY.js.bak` — included `/crank` (unbounded subagents)
- `qa.HEAVY.js.bak` — parallel council-class skills + vibe
- `close-issue.HEAVY.js.bak` — post-mortem council in loop
- `hotfix.HEAVY.js.bak` — vibe security pass on every hotfix
