#!/usr/bin/env python3
"""stale_lease_recovery.py — stale lease recovery manager (P0-CC-005 / ju0o.5).

Sweeps the active-leases ledger for entries that are past their expiry time but
still carry status="active".  Marks them as "expired", records the recovery
reason + timestamp, and writes a recovery artifact.

Only leases whose expiry time is in the past are touched — live leases are
never modified (verified via lease_manager.is_active before skipping).

Usage:
    python scripts/stale_lease_recovery.py scan      # report without mutating
    python scripts/stale_lease_recovery.py recover   # mark stale leases expired
    python scripts/stale_lease_recovery.py recover --reason custom_reason
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import lease_manager as _lm  # noqa: E402

DEFAULT_LEDGER = _lm.DEFAULT_LEDGER
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "collision"
ARTIFACT_PATH = ARTIFACT_DIR / "stale_recovery_latest.json"

DEFAULT_REASON = "ttl_expired"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def scan_stale(ledger: Path | None = None) -> dict[str, Any]:
    """Return a summary of stale (TTL-elapsed but still active) leases.

    Does NOT mutate the ledger.
    """
    ledger = ledger or DEFAULT_LEDGER
    records = _lm.load_ledger(ledger)
    stale: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []

    for r in records:
        if r.get("status") != "active":
            continue
        if _lm.is_active(r):
            active.append(r)
        else:
            stale.append(r)

    return {
        "scanned_at": _now_iso(),
        "ledger": str(ledger),
        "total_active_records": len([r for r in records if r.get("status") == "active"]),
        "stale_count": len(stale),
        "live_count": len(active),
        "stale_leases": [
            {
                "lease_id": r.get("lease_id"),
                "owner_agent": r.get("owner_agent"),
                "task_id": r.get("task_id"),
                "expires_at": r.get("expires_at"),
                "resources": r.get("resources", []),
            }
            for r in stale
        ],
    }


def recover_stale(
    ledger: Path | None = None,
    reason: str = DEFAULT_REASON,
    write_artifact: bool = True,
) -> dict[str, Any]:
    """Expire stale leases and optionally write a recovery artifact.

    Returns a summary matching the scan dict format + ``recovered`` list.
    Active valid leases are never touched.
    """
    ledger = ledger or DEFAULT_LEDGER
    records = _lm.load_ledger(ledger)
    recovered: list[dict[str, Any]] = []
    live_count = 0
    recovered_at = _now_iso()

    for r in records:
        if r.get("status") != "active":
            continue
        if _lm.is_active(r):
            live_count += 1
            continue
        # Stale: mark expired, record reason.
        r["status"] = "expired"
        r["expired_at"] = recovered_at
        r.setdefault("metadata", {})["expire_reason"] = reason
        r["metadata"]["recovered_by"] = "stale_lease_recovery"
        recovered.append(
            {
                "lease_id": r.get("lease_id"),
                "owner_agent": r.get("owner_agent"),
                "task_id": r.get("task_id"),
                "expires_at": r.get("expires_at"),
                "resources": r.get("resources", []),
                "expire_reason": reason,
                "recovered_at": recovered_at,
            }
        )

    if recovered:
        _lm.write_ledger(ledger, records)

    result: dict[str, Any] = {
        "status": "ok",
        "recovered_at": recovered_at,
        "ledger": str(ledger),
        "recovered_count": len(recovered),
        "live_count": live_count,
        "reason": reason,
        "recovered": recovered,
    }

    if write_artifact:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def summarize(ledger: Path | None = None) -> dict[str, Any]:
    """Fail-open stale summary for the harness health dashboard."""
    try:
        info = scan_stale(ledger)
        return {
            "status": "ok" if info["stale_count"] == 0 else "stale_leases_detected",
            "stale_count": info["stale_count"],
            "live_count": info["live_count"],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "stale_count": None, "live_count": None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Stale lease recovery manager (P0-CC-005)")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan")

    p = sub.add_parser("recover")
    p.add_argument("--reason", default=DEFAULT_REASON)
    p.add_argument("--no-artifact", action="store_true")

    sub.add_parser("summarize")

    args = parser.parse_args()
    ledger = Path(args.ledger)

    if args.command == "scan":
        result = scan_stale(ledger)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "recover":
        result = recover_stale(ledger, getattr(args, "reason", DEFAULT_REASON), not args.no_artifact)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "summarize":
        print(json.dumps(summarize(ledger), indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
