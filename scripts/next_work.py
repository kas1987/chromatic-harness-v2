#!/usr/bin/env python3
"""Fallback queue viewer when primary tooling is unavailable."""

from __future__ import annotations

import subprocess
import sys
from typing import NoReturn


def main() -> int | NoReturn:
    # Attempt to list ready/open beads via bd
    result = subprocess.run(
        ["bd", "ready"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
        return 0

    # If bd is absent, surface a clear diagnostic
    print("Queue fallback: bd not available on PATH", file=sys.stderr)
    print("Install beads from https://github.com/steveyegge/beads", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
