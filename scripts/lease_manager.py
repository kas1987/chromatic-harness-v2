#!/usr/bin/env python3
"""Reference lease manager for Chromatic Harness collision control."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO / "01_STATE" / "leases" / "active_leases.jsonl"


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def write_ledger(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + ("\n" if records else ""), encoding="utf-8"
    )


def is_active(record: dict[str, Any]) -> bool:
    if record.get("status") != "active":
        return False
    expires_at = record.get("expires_at", "")
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return expiry > now()


def overlaps(a: str, b: str) -> bool:
    a = a.rstrip("/")
    b = b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def find_conflicts(records: list[dict[str, Any]], resources: list[str], mode: str) -> list[dict[str, Any]]:
    if mode == "read":
        return []
    conflicts = []
    for record in records:
        if not is_active(record):
            continue
        if record.get("mode") == "read":
            continue
        for existing in record.get("resources", []):
            for requested in resources:
                if overlaps(existing, requested):
                    conflicts.append(record)
                    break
    return conflicts


def acquire(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger)
    records = load_ledger(ledger)
    resources = args.resources
    conflicts = find_conflicts(records, resources, args.mode)
    if conflicts:
        print(json.dumps({"status": "denied", "reason": "resource_conflict", "conflicts": conflicts}, indent=2))
        return 2
    lease = {
        "lease_id": f"lease-{uuid.uuid4().hex[:12]}",
        "task_id": args.task_id,
        "owner_agent": args.owner_agent,
        "resources": resources,
        "mode": args.mode,
        "risk_tier": args.risk_tier,
        "status": "active",
        "created_at": iso(now()),
        "expires_at": iso(now() + timedelta(minutes=args.ttl_minutes)),
        "heartbeat_at": iso(now()),
        "rollback_plan": args.rollback_plan,
        "metadata": {},
    }
    records.append(lease)
    write_ledger(ledger, records)
    print(json.dumps({"status": "granted", "lease": lease}, indent=2))
    return 0


def release(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger)
    records = load_ledger(ledger)
    found = False
    for record in records:
        if record.get("lease_id") == args.lease_id and record.get("status") == "active":
            record["status"] = "released"
            record["released_at"] = iso(now())
            found = True
    write_ledger(ledger, records)
    print(json.dumps({"status": "released" if found else "not_found", "lease_id": args.lease_id}, indent=2))
    return 0 if found else 1


def inspect(args: argparse.Namespace) -> int:
    records = load_ledger(Path(args.ledger))
    if args.active_only:
        records = [r for r in records if is_active(r)]
    print(json.dumps(records, indent=2))
    return 0


def expire(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger)
    records = load_ledger(ledger)
    found = False
    for record in records:
        if record.get("lease_id") == args.lease_id and record.get("status") == "active":
            record["status"] = "expired"
            record["expired_at"] = iso(now())
            record.setdefault("metadata", {})["expire_reason"] = args.reason
            found = True
    write_ledger(ledger, records)
    print(json.dumps({"status": "expired" if found else "not_found", "lease_id": args.lease_id}, indent=2))
    return 0 if found else 1


def heartbeat(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger)
    records = load_ledger(ledger)
    found = False
    for record in records:
        if record.get("lease_id") == args.lease_id and record.get("status") == "active":
            record["heartbeat_at"] = iso(now())
            # Renew TTL on heartbeat so a live owner keeps its lease.
            if args.extend_minutes:
                record["expires_at"] = iso(now() + timedelta(minutes=args.extend_minutes))
            found = True
    write_ledger(ledger, records)
    print(json.dumps({"status": "heartbeat" if found else "not_found", "lease_id": args.lease_id}, indent=2))
    return 0 if found else 1


def summarize(ledger: Path | None = None) -> dict:
    """Fail-open lease-status summary for the harness health dashboard (FR-8)."""
    try:
        path = ledger or DEFAULT_LEDGER
        records = load_ledger(path)
        active, stale, conflicts = [], [], []
        for r in records:
            if r.get("status") != "active":
                continue
            (active if is_active(r) else stale).append(r.get("lease_id"))
        # Pairwise overlap among active write/exclusive leases = a live conflict.
        live = [r for r in records if is_active(r) and r.get("mode") != "read"]
        for i, a in enumerate(live):
            for b in live[i + 1 :]:
                if any(overlaps(x, y) for x in a.get("resources", []) for y in b.get("resources", [])):
                    conflicts.append([a.get("lease_id"), b.get("lease_id")])
        return {
            "status": "ok",
            "active_leases": len(active),
            "stale_leases": len(stale),
            "conflicts": len(conflicts),
            "stale_ids": stale,
            "conflict_pairs": conflicts,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "active_leases": None, "stale_leases": None, "conflicts": None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Chromatic Harness lease manager")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("acquire")
    p.add_argument("--task-id", required=True)
    p.add_argument("--owner-agent", required=True)
    p.add_argument("--resources", nargs="+", required=True)
    p.add_argument("--mode", choices=["read", "write", "exclusive", "verify"], required=True)
    p.add_argument("--risk-tier", choices=["T0", "T1", "T2", "T3", "T4"], required=True)
    p.add_argument("--ttl-minutes", type=int, default=60)
    p.add_argument("--rollback-plan", required=True)
    p.set_defaults(func=acquire)

    p = sub.add_parser("release")
    p.add_argument("--lease-id", required=True)
    p.set_defaults(func=release)

    p = sub.add_parser("inspect")
    p.add_argument("--active-only", action="store_true")
    p.set_defaults(func=inspect)

    p = sub.add_parser("expire")
    p.add_argument("--lease-id", required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=expire)

    p = sub.add_parser("heartbeat")
    p.add_argument("--lease-id", required=True)
    p.add_argument("--extend-minutes", type=int, default=0)
    p.set_defaults(func=heartbeat)

    p = sub.add_parser("summarize")
    p.set_defaults(func=lambda a: (print(json.dumps(summarize(Path(a.ledger)), indent=2)), 0)[1])

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
