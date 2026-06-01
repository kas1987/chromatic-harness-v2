#!/usr/bin/env python3
"""check_dirty_state.py — report (and optionally gate on) a dirty working tree.

By default this is advisory: it prints the dirty status but exits 0 so it can
run as a non-blocking informational check. With ``--strict`` it exits 1 when the
working tree is dirty, making it suitable as a hard pre/post-work gate.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common_harness import git_state, repo_root


def main():
    ap = argparse.ArgumentParser(description="Check whether the working tree is dirty.")
    ap.add_argument("--repo-root")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the working tree is dirty (gate mode).",
    )
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    st = git_state(root)

    if st["dirty"]:
        print("Dirty working tree:")
        print("\n".join(st["status_porcelain"]))
        if args.strict:
            return 1
        print("(advisory mode: not failing — pass --strict to gate)")
        return 0

    print("Working tree clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
