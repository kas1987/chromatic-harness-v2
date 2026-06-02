#!/usr/bin/env python3
"""session_status.py — single-pane view of all active sessions in this repo.

Combines:
  - Git worktrees (physical session isolation)
  - Active file-scope leases (agent write claims)
  - Active SQLite session locks (operation serialization)
  - In-progress beads (work queue claims)

Usage:
    python scripts/session_status.py             # human-readable table
    python scripts/session_status.py --json      # machine-readable
    python scripts/session_status.py --conflicts # exit 1 if any conflicts exist
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import lease_manager as _lm  # noqa: E402
from common_harness import run_safe  # noqa: E402

LOCK_DB = REPO / ".agents" / "locks" / "session_locks.sqlite3"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def _collect_worktrees() -> list[dict[str, Any]]:
    try:
        result = run_safe(["git", "worktree", "list", "--porcelain"], cwd=REPO, timeout=10)
        worktrees: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:], "branch": None, "head": None}
            elif line.startswith("branch "):
                current["branch"] = line[7:].replace("refs/heads/", "")
            elif line.startswith("HEAD "):
                current["head"] = line[5:10]
        if current:
            worktrees.append(current)
        return worktrees
    except Exception:  # noqa: BLE001
        return []


def _collect_leases() -> list[dict[str, Any]]:
    try:
        ledger = _lm.DEFAULT_LEDGER
        records = _lm.load_ledger(ledger)
        active = []
        for r in records:
            if _lm.is_active(r):
                active.append(
                    {
                        "lease_id": r.get("lease_id", "?")[:8],
                        "owner": r.get("owner_agent", "unknown"),
                        "mode": r.get("mode", "?"),
                        "resources": r.get("resources", []),
                        "expires_at": r.get("expires_at", ""),
                    }
                )
        return active
    except Exception:  # noqa: BLE001
        return []


def _collect_locks() -> list[dict[str, Any]]:
    if not LOCK_DB.exists():
        return []
    try:
        conn = sqlite3.connect(LOCK_DB, timeout=5.0)
        now_iso = _now().isoformat().replace("+00:00", "Z")
        rows = conn.execute(
            "SELECT lock_name, owner_session_id, acquired_at, expires_at FROM session_locks WHERE expires_at > ?",
            (now_iso,),
        ).fetchall()
        conn.close()
        return [
            {
                "lock_name": r[0],
                "owner_session": r[1][:12] if r[1] else "?",
                "acquired_at": r[2],
                "expires_at": r[3],
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


def _collect_beads() -> list[dict[str, Any]]:
    try:
        result = run_safe(["bd", "list", "--status", "in_progress", "--json"], cwd=REPO, timeout=15)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return [{"id": b.get("id", "?"), "title": b.get("title", "?"), "owner": b.get("owner", "?")} for b in data]
        return []
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _detect_conflicts(leases: list[dict[str, Any]]) -> list[str]:
    """Return human-readable conflict descriptions for overlapping write leases."""
    conflicts: list[str] = []
    write_leases = [l for l in leases if l["mode"] in ("write", "exclusive")]
    for i, a in enumerate(write_leases):
        for b in write_leases[i + 1 :]:
            for ra in a["resources"]:
                for rb in b["resources"]:
                    if _lm.overlaps(ra, rb):
                        conflicts.append(f"{a['owner']} ({a['mode']} on {ra}) ↔ {b['owner']} ({b['mode']} on {rb})")
    return conflicts


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_table(
    worktrees: list[dict],
    leases: list[dict],
    locks: list[dict],
    beads: list[dict],
    conflicts: list[str],
) -> None:
    print("=" * 70)
    print("HARNESS SESSION STATUS")
    print("=" * 70)

    print(f"\n[WORKTREES]  ({len(worktrees)} active)")
    if worktrees:
        for w in worktrees:
            branch = w.get("branch") or "(detached)"
            head = w.get("head") or "?"
            path = w.get("path", "?")
            print(f"  {head}  {branch:<45}  {path}")
    else:
        print("  (none)")

    print(f"\n[FILE LEASES]  ({len(leases)} active)")
    if leases:
        for l in leases:
            resources = ", ".join(l["resources"][:3])
            if len(l["resources"]) > 3:
                resources += f" +{len(l['resources']) - 3} more"
            print(f"  [{l['lease_id']}]  {l['owner']:<20}  {l['mode']:<10}  {resources}")
    else:
        print("  (none)")

    print(f"\n[OPERATION LOCKS]  ({len(locks)} active)")
    if locks:
        for lock in locks:
            print(f"  {lock['lock_name']:<35}  session={lock['owner_session']}")
    else:
        print("  (none)")

    print(f"\n[IN-PROGRESS BEADS]  ({len(beads)} active)")
    if beads:
        for b in beads:
            print(f"  {b['id']:<30}  {b['owner']:<15}  {b['title'][:40]}")
    else:
        print("  (none)")

    if conflicts:
        print(f"\n[CONFLICTS]  *** {len(conflicts)} detected ***")
        for c in conflicts:
            print(f"  CONFLICT: {c}")
    else:
        print("\n[CONFLICTS]  none")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Harness multi-session status")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--conflicts", action="store_true", help="Exit 1 if conflicts exist")
    args = parser.parse_args()

    worktrees = _collect_worktrees()
    leases = _collect_leases()
    locks = _collect_locks()
    beads = _collect_beads()
    conflicts = _detect_conflicts(leases)

    if args.json:
        print(
            json.dumps(
                {
                    "worktrees": worktrees,
                    "leases": leases,
                    "locks": locks,
                    "beads": beads,
                    "conflicts": conflicts,
                },
                indent=2,
            )
        )
        return 1 if (args.conflicts and conflicts) else 0

    _render_table(worktrees, leases, locks, beads, conflicts)
    return 1 if (args.conflicts and conflicts) else 0


if __name__ == "__main__":
    sys.exit(main())
