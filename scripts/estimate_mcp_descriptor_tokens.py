#!/usr/bin/env python3
"""Estimate MCP descriptor bulk — delegates to audit_mcp_context.py."""
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_AUDIT = _REPO / "scripts" / "audit_mcp_context.py"

def main() -> int:
    args = ["--profile", "harness_dev"]
    if len(sys.argv) > 1:
        args = ["--mcps-path", sys.argv[1], *args]
    return subprocess.call([sys.executable, str(_AUDIT), *args], cwd=_REPO)


if __name__ == "__main__":
    raise SystemExit(main())
