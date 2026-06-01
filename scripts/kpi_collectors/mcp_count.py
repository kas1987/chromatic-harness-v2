"""MCP count collector — counts enabled MCP servers from ~/.claude.json."""

import json
import pathlib


def collect():
    config_path = pathlib.Path.home() / ".claude.json"
    if not config_path.exists():
        return {"status": "not_instrumented"}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {"status": "not_instrumented"}

    mcp_servers = data.get("mcpServers", {})
    if not mcp_servers:
        return {"mcp_count": 0, "status": "ok"}

    enabled = [
        name for name, cfg in mcp_servers.items() if not cfg.get("disabled", False)
    ]
    return {"mcp_count": len(enabled), "mcp_servers": enabled, "status": "ok"}


if __name__ == "__main__":
    print(json.dumps(collect()))
