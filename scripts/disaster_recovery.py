#!/usr/bin/env python3
"""Disaster recovery and backup inventory for chromatic-harness-v2 (gh-88).

Modes:
  --inventory   Scan critical state paths, report sizes + last-modified times.
  --backup      Create timestamped snapshot of critical state to a backup location.
  --restore     Print restore procedure (no automatic restore — documented steps only).

Usage:
    python scripts/disaster_recovery.py --inventory
    python scripts/disaster_recovery.py --inventory --json
    python scripts/disaster_recovery.py --backup --dest /path/to/backup/dir
    python scripts/disaster_recovery.py --restore
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# RTO/RPO targets (informational — documented for operators).
RTO_HOURS = 4  # Recovery Time Objective: harness operational within 4 hours
RPO_HOURS = 24  # Recovery Point Objective: max 24 hours of data loss acceptable

# Critical state paths in priority order.
CRITICAL_PATHS: list[dict] = [
    {
        "path": ".beads",
        "description": "Beads issue tracker (local Dolt DB + JSONL export)",
        "priority": "P1",
        "recovery_note": "Restore from .beads/ backup; run `bd dolt pull` to sync remote.",
    },
    {
        "path": ".agents",
        "description": "Agent handoffs, plans, council, harvest, swarm results",
        "priority": "P1",
        "recovery_note": "Restore from backup; re-run `python scripts/session_start.py` to rebuild state.",
    },
    {
        "path": "00_SOURCE_OF_TRUTH",
        "description": "Canon registry, governance truth artifacts",
        "priority": "P1",
        "recovery_note": "Restore from git history or backup snapshot.",
    },
    {
        "path": "07_LOGS_AND_AUDIT",
        "description": "Telemetry, budget ledger, audit trails, security scans",
        "priority": "P2",
        "recovery_note": "Restore from backup. Historical logs not strictly required for operation.",
    },
    {
        "path": "01_STATE",
        "description": "Agent handoff queue, session state",
        "priority": "P2",
        "recovery_note": "Restore from git or backup. Reconstruct queue from beads if lost.",
    },
    {
        "path": "02_RUNTIME",
        "description": "Runtime engines, router config, roach-pi submodule",
        "priority": "P2",
        "recovery_note": "Restore from git checkout + submodule update.",
    },
    {
        "path": ".claude/settings.json",
        "description": "Claude harness settings (hooks, env vars, permissions)",
        "priority": "P1",
        "recovery_note": "Restore from backup. Never commit tokens — redact before backup.",
    },
    {
        "path": "config",
        "description": "Pre-session inventory, config snapshots",
        "priority": "P3",
        "recovery_note": "Regenerate with `python scripts/generate_pre_session_inventory.py`.",
    },
]


def _dir_size(path: Path) -> int:
    """Recursively compute total size of a directory in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except PermissionError:
        pass
    return total


def _last_modified(path: Path) -> str | None:
    """Return ISO timestamp of the most-recently-modified file under path."""
    latest = None
    try:
        if path.is_file():
            return datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc).isoformat()
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    mtime = entry.stat().st_mtime
                    if latest is None or mtime > latest:
                        latest = mtime
                except OSError:
                    pass
    except PermissionError:
        pass
    if latest is None:
        return None
    return datetime.datetime.fromtimestamp(latest, tz=datetime.timezone.utc).isoformat()


def inventory() -> dict:
    """Scan all critical paths and return inventory dict."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    items = []
    total_bytes = 0

    for spec in CRITICAL_PATHS:
        p = REPO / spec["path"]
        exists = p.exists()
        size = _dir_size(p) if exists and p.is_dir() else (p.stat().st_size if exists else 0)
        last_mod = _last_modified(p) if exists else None
        total_bytes += size
        items.append(
            {
                "path": spec["path"],
                "description": spec["description"],
                "priority": spec["priority"],
                "exists": exists,
                "size_bytes": size,
                "size_human": _human_size(size),
                "last_modified": last_mod,
                "recovery_note": spec["recovery_note"],
            }
        )

    result = {
        "schema": "dr_inventory_v1",
        "timestamp": timestamp,
        "repo": str(REPO),
        "rto_hours": RTO_HOURS,
        "rpo_hours": RPO_HOURS,
        "total_critical_bytes": total_bytes,
        "total_critical_human": _human_size(total_bytes),
        "items": items,
    }

    # Write to operations log dir.
    ops_dir = REPO / "07_LOGS_AND_AUDIT" / "operations"
    ops_dir.mkdir(parents=True, exist_ok=True)
    inv_path = ops_dir / "dr_inventory.json"
    inv_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


def backup(dest: str) -> dict:
    """Create a timestamped snapshot of all critical paths to dest/."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_root = Path(dest) / f"chromatic-harness-backup-{timestamp}"
    dest_root.mkdir(parents=True, exist_ok=True)

    results = []
    for spec in CRITICAL_PATHS:
        src = REPO / spec["path"]
        if not src.exists():
            results.append({"path": spec["path"], "status": "skipped_missing"})
            continue
        dst = dest_root / spec["path"]
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            results.append({"path": spec["path"], "status": "ok", "dest": str(dst)})
        except Exception as exc:  # noqa: BLE001
            results.append({"path": spec["path"], "status": "error", "error": str(exc)})

    manifest = {
        "timestamp": timestamp,
        "source_repo": str(REPO),
        "backup_root": str(dest_root),
        "items": results,
    }
    (dest_root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


RESTORE_STEPS = """
RESTORE PROCEDURE — chromatic-harness-v2
=========================================

DO NOT run automated restores without understanding the current repo state.

Step 1: Verify git state
  git status
  git log --oneline -5
  # Confirm you are on the correct branch/commit.

Step 2: Restore critical state from backup snapshot
  BACKUP_ROOT=/path/to/backup/chromatic-harness-backup-<TIMESTAMP>

  # P1 — restore beads (issue tracker)
  cp -r $BACKUP_ROOT/.beads/ ./.beads/
  bd dolt pull            # sync Dolt remote

  # P1 — restore agent state
  cp -r $BACKUP_ROOT/.agents/ ./.agents/

  # P1 — restore source of truth
  cp -r $BACKUP_ROOT/00_SOURCE_OF_TRUTH/ ./00_SOURCE_OF_TRUTH/

  # P1 — restore Claude settings (remove secrets before committing)
  cp $BACKUP_ROOT/.claude/settings.json ./.claude/settings.json

Step 3: Restore P2 state (logs, audit trail, runtime)
  cp -r $BACKUP_ROOT/07_LOGS_AND_AUDIT/ ./07_LOGS_AND_AUDIT/
  cp -r $BACKUP_ROOT/01_STATE/ ./01_STATE/
  cp -r $BACKUP_ROOT/02_RUNTIME/ ./02_RUNTIME/

Step 4: Restore runtime submodule if missing
  git submodule update --init --recursive

Step 5: Validate harness health
  python scripts/harness_health_check.py
  python scripts/validate_claude_harness.py --machine

Step 6: Re-generate derived state
  python scripts/generate_pre_session_inventory.py
  python scripts/session_start.py

Step 7: Verify beads sync
  bd ready
  bd dolt push

RTO target: {rto_hours} hours from incident declaration
RPO target: {rpo_hours} hours maximum data loss
""".format(rto_hours=RTO_HOURS, rpo_hours=RPO_HOURS)


def main() -> int:
    ap = argparse.ArgumentParser(description="Disaster recovery and backup inventory (gh-88)")
    ap.add_argument("--inventory", action="store_true", help="Scan critical paths and write dr_inventory.json")
    ap.add_argument("--backup", action="store_true", help="Create timestamped backup snapshot")
    ap.add_argument(
        "--dest",
        default=os.environ.get("DR_BACKUP_DEST", "/tmp/chromatic-dr-backups"),
        help="Backup destination directory (used with --backup)",
    )
    ap.add_argument("--restore", action="store_true", help="Print restore procedure")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of human-readable text")
    args = ap.parse_args()

    if args.restore:
        print(RESTORE_STEPS)
        return 0

    if args.backup:
        result = backup(args.dest)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Backup complete: {result['backup_root']}")
            ok = sum(1 for i in result["items"] if i["status"] == "ok")
            err = sum(1 for i in result["items"] if i["status"] == "error")
            skip = sum(1 for i in result["items"] if i["status"].startswith("skipped"))
            print(f"  {ok} paths backed up, {skip} skipped (missing), {err} errors")
        return 0

    if args.inventory or not (args.restore or args.backup):
        inv = inventory()
        if args.json:
            print(json.dumps(inv, indent=2))
        else:
            print(f"DR Inventory — {inv['timestamp']}")
            print(f"Repo: {inv['repo']}")
            print(f"RTO: {inv['rto_hours']}h  RPO: {inv['rpo_hours']}h")
            print(f"Total critical state: {inv['total_critical_human']}")
            print()
            print(f"{'PRIORITY':<8} {'PATH':<30} {'SIZE':<12} {'LAST MODIFIED':<25} {'EXISTS'}")
            print("-" * 100)
            for item in inv["items"]:
                mod = (item["last_modified"] or "N/A")[:19]
                print(
                    f"{item['priority']:<8} {item['path']:<30} {item['size_human']:<12} "
                    f"{mod:<25} {'YES' if item['exists'] else 'NO'}"
                )
            ops_path = REPO / "07_LOGS_AND_AUDIT" / "operations" / "dr_inventory.json"
            print(f"\nInventory written to: {ops_path}")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
