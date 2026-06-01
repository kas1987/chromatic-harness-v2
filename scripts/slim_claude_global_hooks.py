#!/usr/bin/env python3
"""Move global Claude SessionStart hooks aside so Harness project boot is lean.

Global ~/.claude/settings.json stacks with project .claude/settings.json. Extra
SessionStart hooks add latency before scripts/session_start.py runs.

Usage:
    python scripts/slim_claude_global_hooks.py --dry-run
    python scripts/slim_claude_global_hooks.py --apply
    python scripts/slim_claude_global_hooks.py --restore
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
GLOBAL_SETTINGS = HOME / ".claude" / "settings.json"
BACKUP = HOME / ".claude" / "settings.json.pre-harness-slim.bak"
ARCHIVE = HOME / ".claude" / "settings.sessionstart-archived.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def dry_run() -> int:
    if not GLOBAL_SETTINGS.is_file():
        print("No global settings at ~/.claude/settings.json — nothing to slim")
        return 0
    doc = _load(GLOBAL_SETTINGS)
    blocks = doc.get("hooks", {}).get("SessionStart", []) or []
    print(f"Global SessionStart blocks: {len(blocks)}")
    for i, block in enumerate(blocks):
        inner = block.get("hooks", [block]) if isinstance(block, dict) else []
        for h in inner:
            if isinstance(h, dict):
                print(f"  [{i}] {h.get('command', '')[:100]}")
    if blocks:
        print("\nApply with: python scripts/slim_claude_global_hooks.py --apply")
    else:
        print("Already slim (no global SessionStart hooks).")
    return 0


def apply() -> int:
    if not GLOBAL_SETTINGS.is_file():
        print("No global settings — skip")
        return 0
    doc = _load(GLOBAL_SETTINGS)
    hooks = doc.setdefault("hooks", {})
    blocks = hooks.get("SessionStart", []) or []
    if not blocks:
        print("Global SessionStart already empty.")
        return 0

    if not BACKUP.is_file():
        shutil.copy2(GLOBAL_SETTINGS, BACKUP)
        print(f"Backup: {BACKUP}")

    archive_doc = {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "reason": "harness_slim_session_start",
        "SessionStart": blocks,
    }
    _save(ARCHIVE, archive_doc)
    print(f"Archived {len(blocks)} SessionStart block(s) to {ARCHIVE}")

    hooks["SessionStart"] = []
    _save(GLOBAL_SETTINGS, doc)
    print(
        "Cleared global SessionStart — Harness project session_start.py owns boot in this repo."
    )
    return 0


def restore() -> int:
    if not BACKUP.is_file():
        print(f"No backup at {BACKUP}", file=sys.stderr)
        return 1
    shutil.copy2(BACKUP, GLOBAL_SETTINGS)
    print(f"Restored global settings from {BACKUP}")
    if ARCHIVE.is_file():
        try:
            archived = _load(ARCHIVE)
            doc = _load(GLOBAL_SETTINGS)
            if archived.get("SessionStart"):
                doc.setdefault("hooks", {})["SessionStart"] = archived["SessionStart"]
                _save(GLOBAL_SETTINGS, doc)
                print("Re-applied archived SessionStart blocks from archive file.")
        except json.JSONDecodeError:
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        return dry_run()
    if args.apply:
        return apply()
    return restore()


if __name__ == "__main__":
    raise SystemExit(main())
