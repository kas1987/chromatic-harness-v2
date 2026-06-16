#!/usr/bin/env python3
"""Sync lite Claude Code workflows from repo -> ~/.claude/workflows/.

Cross-platform Python equivalent of sync_claude_workflows.ps1 so the harness
can self-provision its workflows on any OS (Linux/cloud/macOS/Windows), not
just Windows PowerShell. Backs up existing *.js to *.pre-sync.bak and skips
archived heavy workflows (*.HEAVY.js.bak).

Usage:
  python scripts/sync_claude_workflows.py            # install/refresh
  python scripts/sync_claude_workflows.py --check     # report only, exit 1 if drift
  python scripts/sync_claude_workflows.py --quiet     # suppress per-file output
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / ".claude" / "workflows"
DEST = Path.home() / ".claude" / "workflows"


def _source_workflows() -> list[Path]:
    """Lite *.js workflows to install (excludes archived *.HEAVY.js.bak)."""
    return sorted(p for p in SRC.glob("*.js") if not p.name.endswith(".HEAVY.js.bak"))


def check() -> list[str]:
    """Return names of workflows missing or stale in the install dir."""
    drift: list[str] = []
    for wf in _source_workflows():
        target = DEST / wf.name
        if not target.is_file():
            drift.append(wf.name)
            continue
        if target.read_bytes() != wf.read_bytes():
            drift.append(wf.name)
    return drift


def sync(*, quiet: bool = False) -> int:
    if not SRC.is_dir():
        print(f"Missing source workflows dir: {SRC}", file=sys.stderr)
        return 1

    DEST.mkdir(parents=True, exist_ok=True)

    installed = 0
    for wf in _source_workflows():
        target = DEST / wf.name
        if target.is_file() and target.read_bytes() != wf.read_bytes():
            shutil.copy2(target, target.with_name(target.name + ".pre-sync.bak"))
            if not quiet:
                print(f"Backed up {wf.name} -> {wf.name}.pre-sync.bak")
        shutil.copy2(wf, target)
        installed += 1
        if not quiet:
            print(f"Installed {wf.name}")

    if not quiet:
        print("")
        print(f"Done. Installed {installed} lite workflow(s) to {DEST}.")
        print("Heavy archived workflows (*.HEAVY.js.bak) are NOT installed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync lite Claude workflows to ~/.claude")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift only; exit 1 if any workflow is missing/stale",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress per-file output")
    args = parser.parse_args()

    if args.check:
        drift = check()
        if drift:
            print("Lite workflows missing or stale: " + ", ".join(drift), file=sys.stderr)
            return 1
        if not args.quiet:
            print("Lite workflows up to date.")
        return 0

    return sync(quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
