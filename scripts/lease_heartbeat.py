#!/usr/bin/env python3
"""lease_heartbeat.py — agent heartbeat and renewal (P1-CC-006 / ju0o.6).

Long-running agents renew their lease by emitting a heartbeat: this updates
``heartbeat_at`` and extends ``expires_at`` so the lease is not reaped while the
agent is still alive. Conversely, a lease whose last heartbeat is older than the
grace window is considered abandoned and is marked ``stale`` so the stale-lease
recovery manager (P0-CC-005) can reclaim it.

Wraps lease_manager.py — no new state format; reuses the active_leases ledger.

Usage:
    python scripts/lease_heartbeat.py beat --lease lease-abc123 --extend-minutes 120
    python scripts/lease_heartbeat.py sweep --grace-minutes 15      # report
    python scripts/lease_heartbeat.py sweep --grace-minutes 15 --mark   # mutate
    python scripts/lease_heartbeat.py summarize
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import lease_manager as _lm  # noqa: E402

DEFAULT_LEDGER = _lm.DEFAULT_LEDGER
DEFAULT_GRACE_MINUTES = 15
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "collision"
ARTIFACT_PATH = ARTIFACT_DIR / "heartbeat_latest.json"


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def record_heartbeat(
    lease_id: str,
    ledger: Path | None = None,
    extend_minutes: int = 120,
    *,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Refresh ``heartbeat_at`` and extend ``expires_at`` for *lease_id*.

    Returns {"status": "renewed", ...} or {"status": "not_found", ...}.
    """
    ledger = ledger or DEFAULT_LEDGER
    records = _lm.load_ledger(ledger)
    stamp = timestamp or _lm.now()
    for r in records:
        if r.get("lease_id") == lease_id and r.get("status") == "active":
            r["heartbeat_at"] = _lm.iso(stamp)
            r["expires_at"] = _lm.iso(stamp + timedelta(minutes=extend_minutes))
            _lm.write_ledger(ledger, records)
            return {
                "status": "renewed",
                "lease_id": lease_id,
                "heartbeat_at": r["heartbeat_at"],
                "expires_at": r["expires_at"],
            }
    return {"status": "not_found", "lease_id": lease_id}


def find_missed(
    ledger: Path | None = None,
    grace_minutes: int = DEFAULT_GRACE_MINUTES,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return active leases whose last heartbeat is older than the grace window.

    A lease with no ``heartbeat_at`` falls back to ``created_at``. Leases whose
    timestamps cannot be parsed are treated as alive (fail-open).
    """
    ledger = ledger or DEFAULT_LEDGER
    cutoff = (now or _lm.now()) - timedelta(minutes=grace_minutes)
    missed: list[dict[str, Any]] = []
    for r in _lm.load_ledger(ledger):
        if r.get("status") != "active":
            continue
        last = _parse_iso(r.get("heartbeat_at") or r.get("created_at") or "")
        if last is None:
            continue
        if last < cutoff:
            missed.append(r)
    return missed


def mark_missed_stale(
    ledger: Path | None = None,
    grace_minutes: int = DEFAULT_GRACE_MINUTES,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark leases with missed heartbeats as ``stale`` (recoverable). Mutates."""
    ledger = ledger or DEFAULT_LEDGER
    cutoff = (now or _lm.now()) - timedelta(minutes=grace_minutes)
    records = _lm.load_ledger(ledger)
    marked: list[str] = []
    stamp = _lm.iso(now or _lm.now())
    for r in records:
        if r.get("status") != "active":
            continue
        last = _parse_iso(r.get("heartbeat_at") or r.get("created_at") or "")
        if last is not None and last < cutoff:
            r["status"] = "stale"
            r.setdefault("metadata", {})["stale_reason"] = "missed_heartbeat"
            r["metadata"]["marked_stale_at"] = stamp
            marked.append(r.get("lease_id"))
    if marked:
        _lm.write_ledger(ledger, records)
    return {"status": "ok", "marked_stale": marked, "count": len(marked)}


def summarize(ledger: Path | None = None) -> dict[str, Any]:
    """Fail-open summary for the harness health dashboard + artifact write."""
    try:
        missed = find_missed(ledger)
        result = {
            "status": "ok" if not missed else "missed_heartbeats_detected",
            "missed_count": len(missed),
            "missed_lease_ids": [m.get("lease_id") for m in missed],
        }
    except Exception as exc:  # noqa: BLE001
        result = {"status": "error", "error": str(exc), "missed_count": None}
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent heartbeat and renewal (P1-CC-006)")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("beat")
    b.add_argument("--lease", required=True)
    b.add_argument("--extend-minutes", type=int, default=120)

    s = sub.add_parser("sweep")
    s.add_argument("--grace-minutes", type=int, default=DEFAULT_GRACE_MINUTES)
    s.add_argument("--mark", action="store_true", help="Mark missed leases stale")

    sub.add_parser("summarize")

    args = parser.parse_args()
    ledger = Path(args.ledger)

    if args.command == "beat":
        result = record_heartbeat(args.lease, ledger, args.extend_minutes)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "renewed" else 2

    if args.command == "sweep":
        if args.mark:
            result = mark_missed_stale(ledger, args.grace_minutes)
        else:
            missed = find_missed(ledger, args.grace_minutes)
            result = {"status": "ok", "missed_count": len(missed), "missed": [m.get("lease_id") for m in missed]}
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "summarize":
        print(json.dumps(summarize(ledger), indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
