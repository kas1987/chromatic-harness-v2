#!/usr/bin/env python3
"""Chromatic Harness MCP server (stdio).

Requires: pip install mcp>=1.6.0

See docs/CHROMATIC_MCP_SERVER.md for Cursor configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from chromatic_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
