#!/usr/bin/env python3
"""SessionStart hook: print harness handoff + run bd prime.

Works for Claude Code (.claude/settings.json) and any runner that invokes
this repo's session_start command. Safe when bd is missing (exit 0).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_REPORT = _REPO / "scripts" / "session_context_report.py"
_HANDOFF = _REPO / ".agents" / "handoffs" / "latest.json"
_OPS = _REPO / "AGENT_OPERATIONS.md"
_HYGIENE = _REPO / "docs" / "CURSOR_CONTEXT_HYGIENE.md"


def main() -> int:
    print("=== Chromatic Harness session start ===\n")

    if _HANDOFF.is_file():
        print("--- Handoff (.agents/handoffs/latest.json) ---")
        print(_HANDOFF.read_text(encoding="utf-8").rstrip())
        print()
    else:
        print("(No handoff file — fresh session)\n")

    print("--- Quick refs ---")
    print(f"  Operations: {_OPS.relative_to(_REPO)}")
    print(f"  MCP trim:   {_HYGIENE.relative_to(_REPO)}")
    print("  Audit MCP:  python scripts/audit_mcp_context.py")
    print("  Context:    python scripts/session_context_report.py --log\n")

    runtime = os.environ.get("CHROMATIC_RUNTIME", "claude")
    if _REPORT.is_file():
        subprocess.run(
            [
                sys.executable,
                str(_REPORT),
                "--log",
                "--invoked-by",
                runtime,
            ],
            cwd=_REPO,
            check=False,
        )

    try:
        subprocess.run(["bd", "prime"], cwd=_REPO, check=False)
    except FileNotFoundError:
        print("bd not on PATH — install beads or skip", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
