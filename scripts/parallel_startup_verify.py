#!/usr/bin/env python3
"""Run a compact startup verification for concurrent Harness operation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> dict[str, object]:
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def main() -> int:
    steps = [
        _run([sys.executable, str(REPO / "scripts" / "session_boot_automation.py"), "--invoked-by", "cursor"]),
        _run([sys.executable, str(REPO / "scripts" / "parallel_health.py")]),
        _run([sys.executable, str(REPO / "scripts" / "harness_mcp_tool.py"), "parallel_health"]),
    ]
    out = {
        "ok": all(step["ok"] for step in steps),
        "steps": steps,
    }
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
