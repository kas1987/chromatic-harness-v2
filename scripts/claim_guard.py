#!/usr/bin/env python3
"""claim_guard.py — queue double-claim protection (P0-CC-003 / ju0o.3).

FR-4: a queue item (bead) can have only one active owner. This wraps bead claiming
with an exclusive lease on the resource `queue:<bead_id>` (via lease_manager). A
second agent's claim attempt is deterministically denied and the failed claim is
appended to an audit log.

Network-free; reuses scripts/lease_manager.py for the lease mechanics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO / "01_STATE" / "leases" / "active_leases.jsonl"
CLAIM_LOG = REPO / "07_LOGS_AND_AUDIT" / "claim_guard" / "history.jsonl"


def _lease_manager():
    spec = importlib.util.spec_from_file_location("lease_manager", REPO / "scripts" / "lease_manager.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lease_manager"] = mod
    spec.loader.exec_module(mod)
    return mod


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resource_for(bead_id: str) -> str:
    return f"queue:{bead_id}"


def log_claim(
    action: str,
    bead_id: str,
    agent: str,
    ok: bool,
    detail: str = "",
    *,
    path: Path | None = None,
    timestamp: str | None = None,
) -> None:
    p = path or CLAIM_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "timestamp": timestamp or _now(),
        "action": action,
        "bead_id": bead_id,
        "agent": agent,
        "ok": ok,
        "detail": detail,
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def active_claim(bead_id: str, ledger: Path) -> dict | None:
    """Return the active lease holding this bead's claim, or None."""
    lm = _lease_manager()
    res = resource_for(bead_id)
    for record in lm.load_ledger(ledger):
        if not lm.is_active(record):
            continue
        if res in record.get("resources", []):
            return record
    return None


def claim(
    bead_id: str,
    agent: str,
    ledger: Path | None = None,
    ttl_minutes: int = 120,
    *,
    log_path: Path | None = None,
    timestamp: str | None = None,
) -> dict:
    """Attempt an exclusive claim. Returns {status, ...}. Logs every attempt."""
    ledger = ledger or DEFAULT_LEDGER
    lm = _lease_manager()
    existing = active_claim(bead_id, ledger)
    if existing:
        log_claim(
            "claim_denied",
            bead_id,
            agent,
            False,
            f"held by {existing.get('owner_agent')}",
            path=log_path,
            timestamp=timestamp,
        )
        return {
            "status": "denied",
            "reason": "already_claimed",
            "owner_agent": existing.get("owner_agent"),
            "lease_id": existing.get("lease_id"),
        }

    records = lm.load_ledger(ledger)
    lease = {
        "lease_id": f"lease-{uuid.uuid4().hex[:12]}",
        "task_id": bead_id,
        "owner_agent": agent,
        "resources": [resource_for(bead_id)],
        "mode": "exclusive",
        "risk_tier": "T2",
        "status": "active",
        "created_at": lm.iso(lm.now()),
        "expires_at": lm.iso(lm.now() + timedelta(minutes=ttl_minutes)),
        "heartbeat_at": lm.iso(lm.now()),
        "rollback_plan": "release claim lease",
        "metadata": {"kind": "queue_claim"},
    }
    records.append(lease)
    lm.write_ledger(ledger, records)
    log_claim("claim_granted", bead_id, agent, True, lease["lease_id"], path=log_path, timestamp=timestamp)
    return {"status": "granted", "lease_id": lease["lease_id"], "owner_agent": agent}


def release(
    bead_id: str, ledger: Path | None = None, *, log_path: Path | None = None, timestamp: str | None = None
) -> dict:
    ledger = ledger or DEFAULT_LEDGER
    lm = _lease_manager()
    res = resource_for(bead_id)
    records = lm.load_ledger(ledger)
    found = False
    for record in records:
        if record.get("status") == "active" and res in record.get("resources", []):
            record["status"] = "released"
            record["released_at"] = lm.iso(lm.now())
            found = True
    lm.write_ledger(ledger, records)
    log_claim("claim_released", bead_id, "-", found, "", path=log_path, timestamp=timestamp)
    return {"status": "released" if found else "not_found", "bead_id": bead_id}


def read_log(path: Path | None = None) -> list[dict]:
    p = path or CLAIM_LOG
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Queue double-claim protection (P0-CC-003)")
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("claim")
    c.add_argument("--bead", required=True)
    c.add_argument("--agent", required=True)
    c.add_argument("--ttl-minutes", type=int, default=120)
    r = sub.add_parser("release")
    r.add_argument("--bead", required=True)
    args = ap.parse_args()

    if args.command == "claim":
        result = claim(args.bead, args.agent, ttl_minutes=args.ttl_minutes)
    else:
        result = release(args.bead)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"granted", "released"} else 2


if __name__ == "__main__":
    sys.exit(main())
