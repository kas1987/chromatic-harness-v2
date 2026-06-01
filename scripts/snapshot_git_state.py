#!/usr/bin/env python3
"""snapshot_git_state.py — capture a git-state snapshot for observability.

Records branch, commit, dirty flag, and a breakdown of changed files
(staged / modified / untracked) parsed from ``git status --porcelain``.
Writes JSON to ``--out`` (default ``.chromatic/last_known_good.json``) and
also maintains a stable ``.chromatic/latest_snapshot.json`` pointer so
incident records can always reference the most recent snapshot.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common_harness import git_state, repo_root, utc_now, write_json

LATEST_POINTER = ".chromatic/latest_snapshot.json"


def classify_porcelain(lines):
    """Split ``git status --porcelain`` lines into staged/modified/untracked.

    Porcelain v1 format: two status chars (XY) + space + path. X is the
    index (staged) status, Y is the working-tree status, ``??`` is untracked.
    """
    staged, modified, untracked = [], [], []
    for line in lines:
        if not line:
            continue
        xy = line[:2]
        path = line[3:].strip()
        if xy == "??":
            untracked.append(path)
            continue
        x, y = xy[0], xy[1]
        if x not in (" ", "?"):
            staged.append(path)
        if y not in (" ", "?"):
            modified.append(path)
    return staged, modified, untracked


def build_snapshot(root: Path) -> dict:
    git = git_state(root)
    staged, modified, untracked = classify_porcelain(git.get("status_porcelain", []))
    return {
        "captured_at": utc_now(),
        "repo": root.name,
        "git": git,
        "changed_files": {
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Capture a git-state snapshot.")
    ap.add_argument("--repo-root")
    ap.add_argument("--out", default=".chromatic/last_known_good.json")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()

    snapshot = build_snapshot(root)

    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    write_json(out, snapshot)

    # Always update the stable latest-snapshot pointer for incident linking.
    write_json(root / LATEST_POINTER, {**snapshot, "snapshot_path": str(out)})

    print(out)
    return snapshot


if __name__ == "__main__":
    main()
