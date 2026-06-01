#!/usr/bin/env python3
"""bead_collision_gate.py — cross-check active beads against the lease ledger.

Bridges the gap between the beads work-queue and the harness lease system.
Advisory only (fail-open): if bd is unavailable or the ledger is empty,
the gate passes silently.

Use cases:
  1. Before claiming a bead: check whether another session already holds
     write leases on files that bead's branch would touch.
  2. Before writing a file: check whether an in-progress bead in ANOTHER
     session has a conflicting claim.
  3. CI / session-start: surface any bead ↔ lease mismatches in one view.

Usage:
    python scripts/bead_collision_gate.py check-bead <bead-id>
    python scripts/bead_collision_gate.py check-files <file1> [<file2> ...]
    python scripts/bead_collision_gate.py status          # full cross-check
    python scripts/bead_collision_gate.py status --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import lease_manager as _lm  # noqa: E402
import file_collision_gate as _fcg  # noqa: E402


# ---------------------------------------------------------------------------
# Bead helpers
# ---------------------------------------------------------------------------

def _bd(*args: str, timeout: int = 15) -> tuple[int, str]:
    """Run bd and return (returncode, stdout). Fail-open on any error."""
    try:
        result = subprocess.run(
            ["bd", *args],
            cwd=REPO, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return result.returncode, result.stdout
    except Exception:  # noqa: BLE001
        return -1, ""


def _get_in_progress_beads() -> list[dict[str, Any]]:
    rc, out = _bd("list", "--status", "in_progress", "--json")
    if rc != 0 or not out.strip():
        return []
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _get_bead(bead_id: str) -> dict[str, Any] | None:
    rc, out = _bd("show", bead_id, "--json")
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return None


def _branch_for_bead(bead_id: str) -> str | None:
    """Try to infer the git branch associated with a bead by convention."""
    bead = _get_bead(bead_id)
    if not bead:
        return None
    # Convention: branch name contains bead id slug
    slug = bead_id.split("-")[-1] if "-" in bead_id else bead_id
    try:
        result = subprocess.run(
            ["git", "branch", "--list", f"*{slug}*"],
            cwd=REPO, capture_output=True, text=True, timeout=10, check=False,
        )
        lines = [l.strip().lstrip("* ") for l in result.stdout.splitlines() if l.strip()]
        return lines[0] if lines else None
    except Exception:  # noqa: BLE001
        return None


def _files_touched_by_branch(branch: str) -> list[str]:
    """Return files this branch has changed relative to its merge-base with main."""
    for base in ("origin/main", "origin/master", "main", "master"):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...{branch}"],
                cwd=REPO, capture_output=True, text=True, timeout=15, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return [l.strip() for l in result.stdout.splitlines() if l.strip()]
        except Exception:  # noqa: BLE001
            continue
    return []


# ---------------------------------------------------------------------------
# Cross-check logic
# ---------------------------------------------------------------------------

def _active_write_leases() -> list[dict[str, Any]]:
    ledger = _lm.DEFAULT_LEDGER
    records = _lm.load_ledger(ledger)
    return [r for r in records if _lm.is_active(r) and r.get("mode") in ("write", "exclusive")]


def check_bead(bead_id: str) -> dict[str, Any]:
    """Check whether active leases conflict with the given bead's file scope."""
    branch = _branch_for_bead(bead_id)
    if not branch:
        return {
            "status": "advisory",
            "bead_id": bead_id,
            "message": "No branch found for bead; cannot determine file scope.",
            "conflicts": [],
        }

    files = _files_touched_by_branch(branch)
    if not files:
        return {
            "status": "safe",
            "bead_id": bead_id,
            "branch": branch,
            "message": "No changed files found on branch.",
            "conflicts": [],
        }

    result = _fcg.check_write(files, agent_id=f"bead:{bead_id}")
    conflicts = result.get("conflicts", [])
    return {
        "status": "blocked" if conflicts else "safe",
        "bead_id": bead_id,
        "branch": branch,
        "files_checked": files,
        "conflicts": conflicts,
    }


def check_files(paths: list[str]) -> dict[str, Any]:
    """Check paths against both active leases AND in-progress bead branches."""
    lease_result = _fcg.check_write(paths, agent_id="interactive")
    lease_conflicts = lease_result.get("conflicts", [])

    bead_conflicts: list[dict[str, Any]] = []
    for bead in _get_in_progress_beads():
        bid = bead.get("id", "?")
        branch = _branch_for_bead(bid)
        if not branch:
            continue
        bead_files = _files_touched_by_branch(branch)
        for p in paths:
            for bf in bead_files:
                if _lm.overlaps(p, bf):
                    bead_conflicts.append({
                        "path": p,
                        "bead_id": bid,
                        "bead_file": bf,
                        "bead_branch": branch,
                        "owner": bead.get("owner", "?"),
                    })

    all_clear = not lease_conflicts and not bead_conflicts
    return {
        "status": "safe" if all_clear else "blocked",
        "paths_checked": paths,
        "lease_conflicts": lease_conflicts,
        "bead_conflicts": bead_conflicts,
    }


def full_status() -> dict[str, Any]:
    """Cross-check all in-progress beads against the active lease ledger."""
    beads = _get_in_progress_beads()
    write_leases = _active_write_leases()

    issues: list[dict[str, Any]] = []
    for bead in beads:
        bid = bead.get("id", "?")
        branch = _branch_for_bead(bid)
        if not branch:
            continue
        bead_files = _files_touched_by_branch(branch)
        for lease in write_leases:
            lease_owner = lease.get("owner_agent", "?")
            for resource in lease.get("resources", []):
                for bf in bead_files:
                    if _lm.overlaps(resource, bf):
                        issues.append({
                            "bead_id": bid,
                            "bead_owner": bead.get("owner", "?"),
                            "bead_branch": branch,
                            "bead_file": bf,
                            "lease_id": lease.get("lease_id", "?")[:8],
                            "lease_owner": lease_owner,
                            "lease_resource": resource,
                            "lease_mode": lease.get("mode", "?"),
                        })

    return {
        "status": "conflict" if issues else "ok",
        "in_progress_beads": len(beads),
        "active_write_leases": len(write_leases),
        "bead_lease_conflicts": issues,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Bead ↔ lease cross-check (advisory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-bead", help="Check if a bead's branch conflicts with active leases")
    p.add_argument("bead_id")

    p2 = sub.add_parser("check-files", help="Check files against leases and in-progress bead branches")
    p2.add_argument("paths", nargs="+", metavar="PATH")

    p3 = sub.add_parser("status", help="Full cross-check of all beads vs. lease ledger")
    p3.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "check-bead":
        result = check_bead(args.bead_id)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in ("safe", "advisory") else 2

    if args.command == "check-files":
        result = check_files(args.paths)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "safe" else 2

    if args.command == "status":
        result = full_status()
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            print(f"Bead-lease cross-check: {result['status'].upper()}")
            print(f"  In-progress beads : {result['in_progress_beads']}")
            print(f"  Active write leases: {result['active_write_leases']}")
            if result["bead_lease_conflicts"]:
                print(f"  Conflicts ({len(result['bead_lease_conflicts'])}):")
                for c in result["bead_lease_conflicts"]:
                    print(f"    bead={c['bead_id']} ({c['bead_owner']}) ↔ lease={c['lease_id']} ({c['lease_owner']}) on {c['bead_file']}")
            else:
                print("  No conflicts detected.")
        return 1 if result["status"] == "conflict" else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
