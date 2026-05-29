# Chromatic Harness MCP Server (lite)

Single MCP server exposing the **close-loop** harness tools. Use this instead of enabling many plugin MCPs during daily work.

## Install

```bash
pip install mcp>=1.6.0
```

## Tools

| Tool | Maps to |
|------|---------|
| `workflow_go` | `scripts/workflow_go.py` |
| `workflow_git_ship` | `scripts/workflow_git.py ship` |
| `auto_intake` | `scripts/auto_intake.py` |
| `poll_inbox` | `scripts/poll_inbox.py` |
| `intake_queue_list` | `07_LOGS_AND_AUDIT/intake_queue.jsonl` |
| `beads_ready` | `bd ready` |
| `check_agent_operations` | CI doc guard |
| `validate_intake_loop` | P0 loop validator |

## Cursor configuration

Add to project or user MCP settings (adjust path):

```json
{
  "mcpServers": {
    "chromatic-harness": {
      "command": "python",
      "args": ["scripts/chromatic_mcp_server.py"],
      "cwd": "C:/Users/kas41/chromatic-harness-v2"
    }
  }
}
```

Then **disable** Resend, Playwright, Opsera, and other heavy plugins per [CURSOR_CONTEXT_HYGIENE.md](CURSOR_CONTEXT_HYGIENE.md).

## Run locally (stdio)

```bash
python scripts/chromatic_mcp_server.py
```

## Test handlers without MCP runtime

```bash
pytest tests/test_chromatic_mcp_handlers.py -q
```
