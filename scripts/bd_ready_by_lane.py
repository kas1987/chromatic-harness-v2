#!/usr/bin/env python3
"""Filter `bd ready` output by dual-backlog lane title prefix.

Usage:
  python scripts/bd_ready_by_lane.py --lane agent
  python scripts/bd_ready_by_lane.py --lane human
  python scripts/bd_ready_by_lane.py   # all ready (passthrough)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.lanes import lane_title_prefix  # noqa: E402

_PREFIX_RE = re.compile(r"^\[(agent|human|review)\]", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(description="bd ready filtered by lane")
    parser.add_argument(
        "--lane",
        choices=["agent", "human", "review"],
        default=None,
        help="Filter to this lane only",
    )
    args = parser.parse_args()

    try:
        proc = subprocess.run(
            ["bd", "ready"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        print("bd not found on PATH", file=sys.stderr)
        return 1

    out = proc.stdout or ""
    if proc.returncode != 0:
        print(proc.stderr or out, file=sys.stderr)
        return proc.returncode

    if not args.lane:
        print(out, end="")
        return 0

    prefix = lane_title_prefix(args.lane)
    for line in out.splitlines():
        if _PREFIX_RE.search(line):
            m = _PREFIX_RE.match(line.strip())
            if m and m.group(1).lower() == args.lane:
                print(line)
        elif args.lane == "agent" and not _PREFIX_RE.search(line):
            # Unprefixed work is treated as agent-eligible
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
