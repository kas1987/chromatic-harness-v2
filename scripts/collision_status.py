#!/usr/bin/env python3
"""Collision awareness surface — who holds what right now (OMH-1).

Read-only view over the existing lease ledger (scripts/lease_manager.py). Enforcement
already exists (lease/claim/collision subsystem, P0-CC-*); this adds the missing
*visibility* so agents and humans can see active file claims and live conflicts before
they start work — even when two agents share a branch.

Usage:
  python scripts/collision_status.py            # human table of active leases + conflicts
  python scripts/collision_status.py --json      # machine-readable
  python scripts/collision_status.py --ledger <path>
Exit 0 always (fail-open): a missing/empty ledger means "no active claims".
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from lease_manager import DEFAULT_LEDGER, is_active, load_ledger, overlaps  # noqa: E402


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_minutes(ts: str | None) -> float | None:
    dt = _parse(ts)
    if dt is None:
        return None
    return round((_now() - dt).total_seconds() / 60.0, 1)


def _expires_in_minutes(ts: str | None) -> float | None:
    dt = _parse(ts)
    if dt is None:
        return None
    return round((dt - _now()).total_seconds() / 60.0, 1)


def live_conflicts(active: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pairwise overlap among active non-read leases held by different owners."""
    conflicts = []
    writers = [r for r in active if r.get("mode") != "read"]
    for i, a in enumerate(writers):
        for b in writers[i + 1 :]:
            if a.get("owner_agent") == b.get("owner_agent"):
                continue
            shared = [ra for ra in a.get("resources", []) for rb in b.get("resources", []) if overlaps(ra, rb)]
            if shared:
                conflicts.append(
                    {
                        "owners": [a.get("owner_agent"), b.get("owner_agent")],
                        "leases": [a.get("lease_id"), b.get("lease_id")],
                        "resources": sorted(set(shared)),
                    }
                )
    return conflicts


def build_status(ledger_path: Path) -> dict[str, Any]:
    records = load_ledger(ledger_path)
    active = [r for r in records if is_active(r)]
    holders = [
        {
            "owner_agent": r.get("owner_agent"),
            "task_id": r.get("task_id"),
            "mode": r.get("mode"),
            "resources": r.get("resources", []),
            "age_minutes": _age_minutes(r.get("created_at")),
            "expires_in_minutes": _expires_in_minutes(r.get("expires_at")),
            "lease_id": r.get("lease_id"),
        }
        for r in active
    ]
    holders.sort(key=lambda h: (h["expires_in_minutes"] is None, h["expires_in_minutes"]))
    conflicts = live_conflicts(active)
    return {
        "ledger": str(ledger_path),
        "active_count": len(active),
        "holders": holders,
        "conflicts": conflicts,
        "has_conflicts": bool(conflicts),
    }


def render_table(status: dict[str, Any]) -> str:
    if status["active_count"] == 0:
        return "No active file claims. Safe to acquire a lease."
    lines = [f"Active claims: {status['active_count']}", ""]
    lines.append(f"{'OWNER':<16} {'MODE':<10} {'AGE(m)':>7} {'TTL(m)':>7}  RESOURCES")
    for h in status["holders"]:
        res = ", ".join(h["resources"]) or "(none)"
        age = "-" if h["age_minutes"] is None else h["age_minutes"]
        ttl = "-" if h["expires_in_minutes"] is None else h["expires_in_minutes"]
        lines.append(f"{str(h['owner_agent']):<16} {str(h['mode']):<10} {age:>7} {ttl:>7}  {res}")
    if status["has_conflicts"]:
        lines.append("")
        lines.append(f"⚠ LIVE CONFLICTS ({len(status['conflicts'])}):")
        for c in status["conflicts"]:
            lines.append(f"  {c['owners'][0]} vs {c['owners'][1]} on {', '.join(c['resources'])}")
    else:
        lines.append("")
        lines.append("No live conflicts.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show active file claims / leases and live conflicts.")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    try:
        status = build_status(Path(args.ledger))
    except Exception as exc:  # fail-open: visibility must never block work
        if args.json:
            print(json.dumps({"active_count": 0, "holders": [], "conflicts": [], "error": str(exc)}))
        else:
            print(f"collision_status: unable to read ledger ({exc}); assuming no active claims.")
        return 0

    print(json.dumps(status, indent=2) if args.json else render_table(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
