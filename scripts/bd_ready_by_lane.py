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
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))
sys.path.insert(0, str(REPO / "scripts"))

from activity.lanes import lane_title_prefix  # noqa: E402
from common_harness import run_safe  # noqa: E402

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

    proc = run_safe(["bd", "ready"], cwd=REPO, timeout=30)

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
