# Pre-Session Inventory Config

Machine-readable snapshot and generator settings for documenting what tools, MCP servers, and CRG resources agents are exposed to **before** changing the harness.

## Files

| File | Purpose |
|------|---------|
| `settings.example.yaml` | Template for local MCP descriptors path |
| `settings.local.yaml` | Your machine path (gitignored — copy from example) |
| `inventory.snapshot.json` | Generated JSON baseline (commit after MCP changes) |

## Regenerate

```bash
cp config/pre_session/settings.example.yaml config/pre_session/settings.local.yaml
# Edit mcp_descriptors_path to your Cursor project mcps folder

python scripts/generate_pre_session_inventory.py
```

Or pass path explicitly:

```bash
python scripts/generate_pre_session_inventory.py --mcps-path "$CURSOR_PROJECT_MCPS"
```

## Outputs

- `docs/PRE_SESSION_AND_TOOLS.md` — full reference
- `12_HANDOFFS/PRE_SESSION_INVENTORY.md` — quick index for agents
- `config/pre_session/inventory.snapshot.json` — diffable baseline
