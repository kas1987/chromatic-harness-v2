#!/usr/bin/env python3
"""Cursor sessionStart hook: run harness pre-session boot automation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_BOOT = _REPO / "scripts" / "session_boot_automation.py"


def main() -> int:
    if not _BOOT.is_file():
        print("session_boot_automation.py missing", file=sys.stderr)
        return 0
    r = subprocess.run(
        [sys.executable, str(_BOOT), "--invoked-by", "cursor"],
        cwd=_REPO,
        timeout=120,
        check=False,
    )
    return 0 if r.returncode in (0, 124) else 0


if __name__ == "__main__":
    raise SystemExit(main())
