---
title: MCP stdio one-shot client lifecycle
date: 2026-04-26
category: implementation
tags: [mcp, stdio, subprocess, python, lifecycle, integration]
confidence: high
source: whisper-call v0.2 — fix commit 75d5260
related: [mcp-sdk, anthropic-mcp, subprocess]
---

# MCP stdio one-shot client lifecycle

## What we learned

When invoking a `@modelcontextprotocol/sdk` stdio MCP server from a non-MCP-aware
client (e.g. a Python CLI tool wanting one tool call and exit), `subprocess.run`
will always block until the timeout. The MCP SDK does **not** treat stdin EOF
as a shutdown signal — the server keeps the event loop alive waiting for more
JSON-RPC frames.

## Why it matters

Every CLI invocation that touches MCP this way pays a 60s (or whatever timeout)
penalty per call. Symptom: feature appears broken / slow even though tests pass
in isolation. In our case, the entire CLI driver path was effectively unusable
until we noticed the integration timing.

## Pattern: one-shot Popen + terminate

```python
def call_mcp_oneshot(tool: str, args: dict, mcp_path: str, request_id: int = 1) -> dict:
    """Call a single MCP tool from a non-persistent client."""
    request = {
        "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }

    try:
        proc = subprocess.Popen(
            ["node", mcp_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
    except (FileNotFoundError, OSError) as err:
        return {"error": f"MCP subprocess spawn failed: {err}"}

    try:
        proc.stdin.write(json.dumps(request) + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if "result" in response:
                content = response["result"].get("content", [])
                if content and content[0].get("type") == "text":
                    return json.loads(content[0]["text"])
            if "error" in response:
                return {"error": f"MCP error: {response['error']}"}
        return {"error": "MCP subprocess exited before response"}
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            try:
                proc.kill()
            except Exception:
                pass
```

## Defense-in-depth notes

- **`bufsize=1`** requests line-buffering. Real-world buffering depends on the
  child runtime; iterating `for line in proc.stdout` works regardless.
- **`terminate() + wait(timeout=2)` then `kill()` fallback** — Windows does not
  always honor SIGTERM cleanly on `node.exe`; the `kill()` fallback prevents
  orphan processes.
- **`response.get("id") != request_id`** — match by id, not order. The MCP SDK
  may emit log frames or notifications before the response.

## Anti-pattern (what NOT to do)

```python
# DOES NOT WORK — always hits timeout
proc = subprocess.run(
    ["node", mcp_path],
    input=json.dumps(request) + "\n",
    capture_output=True, text=True, timeout=60,
)
```

`subprocess.run` writes stdin and closes it but the MCP SDK never observes EOF
as a shutdown trigger. The 60s timeout fires every time.

## When to use this pattern vs alternatives

- **One-shot Popen (this pattern):** simple, isolated, ~30 lines. Right when
  the client makes 1-3 MCP calls per CLI invocation.
- **Long-lived subprocess pool:** cache one MCP subprocess and reuse across
  calls. Right when the client makes >5 calls or latency-sensitive.
- **Native MCP client integration:** use the official `@modelcontextprotocol/sdk`
  client library (Python or TS). Right when the client is itself MCP-aware
  (Claude Code, Cursor, etc.).

## Source

- Bug discovered: whisper-call v0.1 plan Task 18 (called out as "to address in Task 26")
- Fixed: whisper-call v0.2 (commit 75d5260, 2026-04-26)
- Real-world impact: 60s → 411ms (146× faster) for `python call_driver.py get-mode`
