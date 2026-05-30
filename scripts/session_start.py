#!/usr/bin/env python3
"""SessionStart hook: handoff, automated pre-session boot, bd prime.

Works for Claude Code (.claude/settings.json) and any runner that invokes
this repo's session_start command. Safe when bd is missing (exit 0).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BOOT = _REPO / "scripts" / "session_boot_automation.py"
_HANDOFF = _REPO / ".agents" / "handoffs" / "latest.json"
_OPS = _REPO / "AGENT_OPERATIONS.md"
_MANIFEST = _REPO / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"


def main() -> int:
    print("=== Chromatic Harness session start ===\n")

    if _HANDOFF.is_file():
        print("--- Handoff (.agents/handoffs/latest.json) ---")
        print(_HANDOFF.read_text(encoding="utf-8").rstrip())
        print()
    else:
        print("(No handoff file — fresh session)\n")

    print("--- Automated pre-session boot ---")
    runtime = os.environ.get("CHROMATIC_RUNTIME", "claude")
    if _BOOT.is_file():
        r = subprocess.run(
            [sys.executable, str(_BOOT), "--invoked-by", runtime],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0 and r.stderr:
            print(r.stderr.strip(), file=sys.stderr)
    else:
        print("  (session_boot_automation.py not found — skip)")

    print(f"\n--- Operations: {_OPS.relative_to(_REPO)} ---")
    if _MANIFEST.is_file():
        try:
            m = json.loads(_MANIFEST.read_text(encoding="utf-8"))
            print(f"  Manifest: {_MANIFEST.relative_to(_REPO)}")
            print(f"  generated_at: {m.get('generated_at')}")
            print(f"  branch: {m.get('branch')}")
            tok = m.get("mcp_audit", {}).get("estimated_tokens_if_enabled")
            if tok is not None:
                print(f"  MCP est. tokens: {tok:,}")
        except (json.JSONDecodeError, OSError):
            print(f"  Manifest: {_MANIFEST.relative_to(_REPO)}")
    else:
        print("  Manifest: (not written yet)")
    print()

    try:
        subprocess.run(["bd", "prime"], cwd=_REPO, check=False)
    except FileNotFoundError:
        print("bd not on PATH — install beads or skip", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
