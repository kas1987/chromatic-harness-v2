#!/usr/bin/env python3
"""emergency_recovery.py — emergency recovery command (k9j7 / gh-108).

Implements the recovery modes + stop-conditions defined in
docs/governance/CLAUDE_RECOVERY_PROCEDURES.md. This is the authority-delegating
backend for the `/recover` adapter command: it does NOT reimplement recovery
logic — it orchestrates the existing harness tools (lease_manager,
harness_health_check, stale_lease_recovery) and enforces the policy gates.

Recovery modes:
  1. Inspect Only (default, read-only)              — `inspect`
  2. Stale Lease Recovery (gated, requires evidence) — `stale-lease`

Mutating actions are refused unless --apply is set AND every stop condition is
clear AND full evidence (lease id, owner, reason, rollback note) is supplied.
Every action — allowed or refused — is appended to the recovery audit log.

Network-free; reuses scripts/lease_manager.py + scripts/harness_health_check.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RECOVERY_DIR = REPO / "07_LOGS_AND_AUDIT" / "recovery"
RECOVERY_LOG = RECOVERY_DIR / "recovery_log.jsonl"
ARTIFACT_PATH = RECOVERY_DIR / "latest.json"

# Stop conditions from CLAUDE_RECOVERY_PROCEDURES.md — recovery halts if any hold.
STOP_REASONS = {
    "active_owner": "lease is active and owner may still be working",
    "missing_rollback": "rollback plan is missing",
    "secrets": "failure affects secrets",
    "delete_requested": "recovery requires deleting files/branches",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _lease_manager():
    return _load("lease_manager", "scripts/lease_manager.py")


def log_recovery(
    action: str,
    ok: bool,
    detail: str = "",
    *,
    mode: str = "inspect",
    path: Path | None = None,
    timestamp: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a recovery action to the audit log (matches registry logs_to)."""
    p = path or RECOVERY_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "timestamp": timestamp or _now_iso(),
        "action": action,
        "mode": mode,
        "ok": ok,
        "detail": detail,
    }
    if extra:
        rec.update(extra)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def assess_stop_conditions(
    *,
    target_lease: dict[str, Any] | None = None,
    rollback_plan: str | None = None,
    affects_secrets: bool = False,
    delete_requested: bool = False,
    ledger: Path | None = None,
) -> list[str]:
    """Return the list of triggered stop-condition keys (empty = clear to proceed)."""
    lm = _lease_manager()
    triggered: list[str] = []
    if target_lease is not None and lm.is_active(target_lease):
        triggered.append("active_owner")
    if not rollback_plan:
        triggered.append("missing_rollback")
    if affects_secrets:
        triggered.append("secrets")
    if delete_requested:
        triggered.append("delete_requested")
    return triggered


def inspect(ledger: Path | None = None) -> dict[str, Any]:
    """Read-only recovery assessment: health + lease state + recommendations."""
    lm = _lease_manager()
    lease_summary = lm.summarize(ledger)
    records = lm.load_ledger(ledger or lm.DEFAULT_LEDGER)
    active = [r for r in records if lm.is_active(r)]

    recommendations: list[str] = []
    stale = lease_summary.get("stale_leases", 0) or 0
    conflicts = lease_summary.get("conflicts", 0) or 0
    if conflicts:
        recommendations.append(f"{conflicts} active lease conflict(s) — inspect overlapping owners before any action")
    if stale:
        recommendations.append(
            f"{stale} stale lease(s) — eligible for `stale-lease` recovery with evidence + rollback note"
        )
    if not recommendations:
        recommendations.append("no recovery action required (no stale leases or conflicts)")

    result = {
        "mode": "inspect",
        "generated_at": _now_iso(),
        "lease_summary": lease_summary,
        "active_lease_count": len(active),
        "active_leases": [
            {
                "lease_id": r.get("lease_id"),
                "owner_agent": r.get("owner_agent"),
                "resources": r.get("resources", []),
                "expires_at": r.get("expires_at"),
            }
            for r in active
        ],
        "stale_count": stale,
        "conflict_count": conflicts,
        "recommendations": recommendations,
    }
    return result


def recover_stale_lease(
    lease_id: str,
    owner_agent: str,
    reason: str,
    rollback_plan: str,
    *,
    apply: bool = False,
    affects_secrets: bool = False,
    ledger: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Recover a stale lease, gated by evidence + stop conditions.

    Refused (no mutation) when: the lease is missing, still active (owner may be
    working), rollback note is absent, secrets involved, or apply is not set.
    """
    lm = _lease_manager()
    led = ledger or lm.DEFAULT_LEDGER
    records = lm.load_ledger(led)
    target = next((r for r in records if r.get("lease_id") == lease_id), None)

    if target is None:
        out = {"status": "not_found", "lease_id": lease_id}
        log_recovery(
            "stale_lease_recovery",
            False,
            f"lease {lease_id} not found",
            mode="stale-lease",
            path=log_path,
            extra={"lease_id": lease_id},
        )
        return out

    stops = assess_stop_conditions(
        target_lease=target,
        rollback_plan=rollback_plan,
        affects_secrets=affects_secrets,
        ledger=led,
    )
    if stops:
        out = {
            "status": "blocked",
            "lease_id": lease_id,
            "stop_conditions": stops,
            "reasons": [STOP_REASONS[s] for s in stops],
        }
        log_recovery(
            "stale_lease_recovery",
            False,
            f"blocked: {','.join(stops)}",
            mode="stale-lease",
            path=log_path,
            extra={"lease_id": lease_id, "stop_conditions": stops},
        )
        return out

    if not apply:
        out = {
            "status": "dry_run",
            "lease_id": lease_id,
            "would_expire": True,
            "owner_agent": owner_agent,
            "reason": reason,
        }
        log_recovery(
            "stale_lease_recovery",
            True,
            "dry-run (stop conditions clear)",
            mode="stale-lease",
            path=log_path,
            extra={"lease_id": lease_id},
        )
        return out

    # Delegate to harness authority (lease_manager.expire) rather than mutating here.
    ns = argparse.Namespace(ledger=str(led), lease_id=lease_id, reason=reason)
    rc = lm.expire(ns)
    ok = rc == 0
    out = {
        "status": "expired" if ok else "expire_failed",
        "lease_id": lease_id,
        "owner_agent": owner_agent,
        "reason": reason,
        "rollback_plan": rollback_plan,
    }
    log_recovery(
        "stale_lease_recovery",
        ok,
        f"expired via lease_manager ({reason})",
        mode="stale-lease",
        path=log_path,
        extra={"lease_id": lease_id, "rollback_plan": rollback_plan},
    )
    return out


def summarize(ledger: Path | None = None) -> dict[str, Any]:
    """Fail-open recovery summary + artifact write for the health dashboard."""
    try:
        info = inspect(ledger)
        result = {
            "status": "ok",
            "stale_count": info["stale_count"],
            "conflict_count": info["conflict_count"],
            "active_lease_count": info["active_lease_count"],
            "action_required": info["stale_count"] > 0 or info["conflict_count"] > 0,
        }
    except Exception as exc:  # noqa: BLE001
        result = {"status": "error", "error": str(exc), "action_required": None}
    try:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return result


def read_log(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or RECOVERY_LOG
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
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
    parser = argparse.ArgumentParser(description="Emergency recovery command (k9j7)")
    parser.add_argument("--ledger", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inspect")
    sub.add_parser("summarize")

    s = sub.add_parser("stale-lease")
    s.add_argument("--lease-id", required=True)
    s.add_argument("--owner-agent", required=True)
    s.add_argument("--reason", required=True)
    s.add_argument("--rollback-plan", required=True)
    s.add_argument("--affects-secrets", action="store_true")
    s.add_argument("--apply", action="store_true")

    args = parser.parse_args()
    ledger = Path(args.ledger) if args.ledger else None

    if args.command == "inspect":
        print(json.dumps(inspect(ledger), indent=2))
        return 0
    if args.command == "summarize":
        print(json.dumps(summarize(ledger), indent=2))
        return 0
    if args.command == "stale-lease":
        result = recover_stale_lease(
            args.lease_id,
            args.owner_agent,
            args.reason,
            args.rollback_plan,
            apply=args.apply,
            affects_secrets=args.affects_secrets,
            ledger=ledger,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in {"expired", "dry_run"} else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
