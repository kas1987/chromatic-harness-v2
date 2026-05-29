# Pre-Session Inventory (Quick Reference)

> Full doc: [docs/PRE_SESSION_AND_TOOLS.md](../docs/PRE_SESSION_AND_TOOLS.md)  
> Generated: `2026-05-29T01:24:16.995915+00:00`

## At a glance

| Category | Count |
|----------|------:|
| Native tools | 15 |
| MCP servers | 1 |
| MCP tools | 1 |
| CRG resources | 15 |

## Before changing tools or MCP

1. `python scripts/generate_pre_session_inventory.py`
2. Review diff in `config/pre_session/inventory.snapshot.json`
3. Update CRG policy if needed

## Session start

```bash
cat .agents/handoffs/latest.json
bd ready
```

See [SESSION_COMPACT.md](SESSION_COMPACT.md) for compaction protocol.
