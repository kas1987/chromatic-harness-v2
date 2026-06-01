#!/usr/bin/env python3
"""update_last_known_good.py — record a *validated clean* checkpoint.

A last-known-good (LKG) checkpoint should only be recorded when the working
tree is clean, so that rollback targets are trustworthy. This refuses to write
when the repo is dirty unless ``--force`` is given, and stamps the checkpoint
with ``validated`` / ``forced`` flags.

Writes to ``--out`` (default ``.chromatic/last_known_good.json``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common_harness import repo_root, write_json
from snapshot_git_state import build_snapshot


def main():
    ap = argparse.ArgumentParser(description="Record a validated last-known-good checkpoint.")
    ap.add_argument("--repo-root")
    ap.add_argument("--out", default=".chromatic/last_known_good.json")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Record the checkpoint even if the working tree is dirty.",
    )
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()

    snapshot = build_snapshot(root)
    dirty = bool(snapshot["git"].get("dirty"))

    if dirty and not args.force:
        print(
            "Refusing to record last-known-good: working tree is dirty. Commit/stash changes or pass --force.",
            file=sys.stderr,
        )
        return 1

    checkpoint = {
        **snapshot,
        "checkpoint": "last_known_good",
        "validated": not dirty,
        "forced": bool(dirty and args.force),
    }

    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    write_json(out, checkpoint)
    print(f"Recorded last-known-good checkpoint: {out} (validated={checkpoint['validated']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
