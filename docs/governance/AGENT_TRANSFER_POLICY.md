# Agent Transfer Policy

## Purpose

At session end, the harness **must** externalize state and optionally **spawn a successor agent** only when monthly, daily, and session budgets allow.

Authority: [12_HANDOFFS/SESSION_COMPACT.md](../../12_HANDOFFS/SESSION_COMPACT.md), [AGENT_TRANSFER_PACKET_SCHEMA.md](AGENT_TRANSFER_PACKET_SCHEMA.md), [config/agent_budget.yaml](../../config/agent_budget.yaml).

## One command

```bash
python scripts/session_closeout.py --invoked-by cursor
```

IDE hooks and Task Scheduler call the same script (see [IDE_CLI_PARITY_POLICY.md](IDE_CLI_PARITY_POLICY.md)).

## Budget tiers

| Tier | Measurement | Storage |
|------|-------------|---------|
| Session | MCP/context estimate + activity events this closeout | ATP snapshot |
| Daily | `CHROMATIC_ROUTER_DAILY_SPEND` + ledger append | `07_LOGS_AND_AUDIT/budget/daily.jsonl` |
| Monthly | Sum of daily ledger for calendar month | `07_LOGS_AND_AUDIT/budget/monthly.json` |

Phase B: ingest Claude `usage-tracker.sh` output when present.  
Phase C: `session_closeout.py --with-api` for OpenRouter live burn (optional).

## Transfer decisions

`decide_transfer()` in `02_RUNTIME/budget/ledger.py`:

| Decision | When |
|----------|------|
| `halt_human` | Monthly or daily cap exhausted |
| `handoff_only` | Session ≥ `handoff_only_below_session_pct` of cap, or remaining daily/monthly below spawn thresholds |
| `spawn` | All caps have headroom after `successor_reserve_usd` |

## Auto-spawn

Enabled when:

- `budget.decision == spawn`
- `CHROMATIC_AUTO_SPAWN=1` (default off in CI)
- Adapter available or falls back to manual bead

Env:

- `CHROMATIC_AUTO_SPAWN=1`
- `CHROMATIC_SUCCESSOR_RUNTIME=cursor|claude_code`
- `CURSOR_API_KEY` for Cursor SDK adapter

Closeout **never fails** if spawn fails; it logs and creates a beads follow-up.

## Parity surfaces

| Surface | Trigger |
|---------|---------|
| Cursor | `.cursor/hooks.json` `sessionEnd` |
| Claude Code | `SessionEnd` → `.claude/hooks/session_closeout.sh` |
| VS Code | Task "Harness: Session Closeout" |
| Scheduler | `ChromaticSessionCloseout` daily task |

## Forbidden at handoff

- Pasting full `~/.claude/projects/**/*.jsonl`
- Bulk-loading `07_LOGS_AND_AUDIT/**/*.jsonl` into successor context
- Chat-only state without beads + handoff files
