#!/usr/bin/env python3
"""Cursor sessionEnd hook: budget-aware session closeout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CLOSEOUT = _REPO / "scripts" / "session_closeout.py"


def main() -> int:
    if not _CLOSEOUT.is_file():
        return 0
    r = subprocess.run(
        [sys.executable, str(_CLOSEOUT), "--invoked-by", "cursor"],
        cwd=_REPO,
        timeout=180,
        check=False,
    )
    return 0 if r.returncode in (0, 124) else 0


if __name__ == "__main__":
    raise SystemExit(main())
