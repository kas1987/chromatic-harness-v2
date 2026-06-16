#!/usr/bin/env python3
"""Shared log-retention / rotation helper for 07_LOGS_AND_AUDIT.

Single source of retention logic so every per-run writer stops growing
unbounded. Either call ``prune_dir(...)`` from a writer after it writes, or
run this module as a CLI to sweep a folder (or all configured folders) on a
schedule / in session closeout.

Policy (best-practice defaults):
  - Always KEEP files matching the protect globs: latest.json, *_latest.json,
    history.jsonl, *.md, .gitkeep, .gitignore, *.yaml, *.yml, *schema*.
  - From the remaining (dated/per-run) files, keep the newest ``keep`` by
    mtime, and optionally drop anything older than ``keep_days``.
  - Fail-open: any error logs to stderr and returns without raising, so a
    retention failure never blocks the hot path (Definition of Done, step 7).

Safety:
  - Dry-run by DEFAULT. Pass ``apply=True`` (CLI: --apply) to actually delete.
  - Optional ``archive_dir`` tars deleted files before unlinking.

Usage:
    # preview what would be pruned in one folder
    python scripts/log_retention.py 07_LOGS_AND_AUDIT/token_governance
    # actually prune, keeping newest 50, archiving first
    python scripts/log_retention.py 07_LOGS_AND_AUDIT/token_governance \
        --keep 50 --apply --archive ~/harness_cleanup_archive
    # sweep every configured exhaust folder
    python scripts/log_retention.py --all --keep 50 --apply
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import tarfile
import time
from pathlib import Path

DEFAULT_KEEP = 50
DEFAULT_PROTECT = (
    "latest.json", "*_latest.json", "history.jsonl",
    "*.md", ".gitkeep", ".gitignore", "*.yaml", "*.yml", "*schema*",
)

# Folders (relative to repo root) that produce unbounded per-run exhaust.
# Wire new writers here so --all keeps covering them.
MANAGED_DIRS = {
    "07_LOGS_AND_AUDIT/token_governance": dict(keep=50),
    "07_LOGS_AND_AUDIT/unified_guard": dict(keep=50),
    "07_LOGS_AND_AUDIT/governance_intelligence": dict(keep=50),
    "07_LOGS_AND_AUDIT/security": dict(keep=50),
    "07_LOGS_AND_AUDIT/ci": dict(keep=50),
    "07_LOGS_AND_AUDIT/pre_session": dict(keep=30),
    "07_LOGS_AND_AUDIT/routing": dict(keep=30),
    "07_LOGS_AND_AUDIT/ws_events": dict(keep=5),
}


def _is_protected(name: str, protect) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in protect)


def prune_dir(
    directory,
    keep: int = DEFAULT_KEEP,
    keep_days: float | None = None,
    protect=DEFAULT_PROTECT,
    apply: bool = False,
    archive_dir=None,
):
    """Prune per-run files in *directory*. Returns (kept, removed, bytes_freed).

    Fail-open: never raises; on error returns (0, 0, 0) and logs to stderr.
    """
    try:
        d = Path(directory)
        if not d.is_dir():
            return (0, 0, 0)
        candidates = []
        for p in d.iterdir():
            if not p.is_file():
                continue
            if _is_protected(p.name, protect):
                continue
            candidates.append(p)
        # newest first
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        to_remove = list(candidates[keep:])
        if keep_days is not None:
            cutoff = time.time() - keep_days * 86400
            extra = [p for p in candidates[:keep] if p.stat().st_mtime < cutoff]
            to_remove.extend(extra)
        to_remove = sorted(set(to_remove))

        bytes_freed = sum(p.stat().st_size for p in to_remove)

        if to_remove and apply and archive_dir:
            adir = Path(archive_dir)
            adir.mkdir(parents=True, exist_ok=True)
            tar_path = adir / f"{d.name}_pruned.tar.gz"
            mode = "a:gz" if False else "w:gz"  # fresh archive per run
            with tarfile.open(tar_path, mode) as tar:
                for p in to_remove:
                    tar.add(p, arcname=p.name)

        removed = 0
        if apply:
            for p in to_remove:
                try:
                    p.unlink()
                    removed += 1
                except OSError as exc:  # pragma: no cover
                    print(f"[log_retention] could not unlink {p}: {exc}", file=sys.stderr)
        else:
            removed = len(to_remove)  # would-remove count in dry-run

        kept = len(candidates) - len(to_remove)
        return (kept, removed, bytes_freed)
    except Exception as exc:  # fail-open
        print(f"[log_retention] prune_dir error on {directory}: {exc}", file=sys.stderr)
        return (0, 0, 0)


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Prune per-run exhaust in 07_LOGS_AND_AUDIT.")
    ap.add_argument("directory", nargs="?", help="folder to prune (omit with --all)")
    ap.add_argument("--all", action="store_true", help="prune every MANAGED_DIRS folder")
    ap.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    ap.add_argument("--keep-days", type=float, default=None)
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--archive", default=None, help="tar deleted files here before unlink")
    args = ap.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    targets = []
    if args.all:
        targets = [(repo / rel, cfg.get("keep", args.keep)) for rel, cfg in MANAGED_DIRS.items()]
    elif args.directory:
        targets = [(Path(args.directory), args.keep)]
    else:
        ap.error("give a directory or --all")

    total_removed = total_bytes = 0
    verb = "removed" if args.apply else "would remove"
    for path, keep in targets:
        kept, removed, freed = prune_dir(
            path, keep=keep, keep_days=args.keep_days,
            apply=args.apply, archive_dir=args.archive,
        )
        total_removed += removed
        total_bytes += freed
        print(f"{path}: kept {kept}, {verb} {removed} ({_human(freed)})")
    print(f"TOTAL: {verb} {total_removed} files, {_human(total_bytes)}"
          + ("" if args.apply else "  [dry-run; pass --apply]"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
