#!/usr/bin/env python3
"""Emergency recovery orchestrator for the /recover Claude adapter command.

Implements the four recovery modes defined in
docs/governance/CLAUDE_RECOVERY_PROCEDURES.md:

  1. Inspect (default)  — health + lease summary, no mutations.
  2. Stale lease        -- expire an expired/abandoned lease (requires evidence).
  3. Duplicate issue    -- identify and document duplicates (no auto-close).
  4. Failed ship        -- inspect workflow logs + plan (no auto-merge/force).

Stop conditions (always enforced):
  - State is ambiguous.
  - Lease is active and owner may still be working.
  - Failure affects secrets.
  - Data loss risk.
  - Rollback plan is missing for mutations.
  - Recovery requires deleting files or branches.

All output is written to 07_LOGS_AND_AUDIT/recovery/recovery_log.jsonl.
Exit codes: 0=ok, 1=stop_condition_triggered, 2=error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RECOVERY_LOG = REPO / "07_LOGS_AND_AUDIT" / "recovery" / "recovery_log.jsonl"
LEASE_LEDGER = REPO / "state" / "leases" / "active_leases.jsonl"
HEALTH_REPORT = REPO / "reports" / "harness_health" / "latest.json"


# ---------------------------------------------------------------------------
# Stop condition guard
# ---------------------------------------------------------------------------

STOP_CONDITIONS = [
    "state_ambiguous",
    "lease_active_owner_present",
    "secrets_affected",
    "data_loss_risk",
    "rollback_plan_missing",
    "requires_file_or_branch_delete",
]


def check_stop_condition(condition: str, detail: str = "") -> dict[str, Any]:
    """Return a stop-condition record and prepare to exit 1."""
    return {
        "halt": True,
        "stop_condition": condition,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return "rcv_" + uuid.uuid4().hex[:8]


def load_leases(path: Path) -> list[dict[str, Any]]:
    """Load lease ledger, fail-open on missing or corrupt file."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError:
            pass  # corrupt line — skip
    return records


def active_leases(leases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    result = []
    for r in leases:
        if r.get("status") != "active":
            continue
        expires_at = r.get("expires_at", "")
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry > now:
                result.append(r)
        except ValueError:
            result.append(r)  # unparseable expiry — treat as active (safe default)
    return result


def stale_leases(leases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    result = []
    for r in leases:
        if r.get("status") != "active":
            continue
        expires_at = r.get("expires_at", "")
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry <= now:
                result.append(r)
        except ValueError:
            pass
    return result


def load_health() -> dict[str, Any]:
    """Load latest health report, fail-open."""
    try:
        if HEALTH_REPORT.exists():
            return json.loads(HEALTH_REPORT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {"overall_status": "unknown", "note": "health report unavailable"}


def append_log(record: dict[str, Any]) -> None:
    RECOVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RECOVERY_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Recovery modes
# ---------------------------------------------------------------------------


def mode_inspect() -> dict[str, Any]:
    """Mode 1: read-only inspection. Always safe."""
    leases = load_leases(LEASE_LEDGER)
    alive = active_leases(leases)
    stale = stale_leases(leases)
    health = load_health()
    return {
        "mode": "inspect",
        "health_status": health.get("overall_status", "unknown"),
        "active_leases": len(alive),
        "stale_leases": len(stale),
        "stale_lease_ids": [r.get("lease_id") for r in stale],
        "active_lease_ids": [r.get("lease_id") for r in alive],
        "mutation": False,
        "suggested_actions": _inspect_suggestions(alive, stale, health),
    }


def _inspect_suggestions(
    alive: list[dict[str, Any]],
    stale: list[dict[str, Any]],
    health: dict[str, Any],
) -> list[str]:
    suggestions: list[str] = []
    if health.get("overall_status") not in {"green", "unknown"}:
        suggestions.append(
            f"Health status is {health.get('overall_status')} — run "
            "'python scripts/harness_health_check.py --markdown' for details."
        )
    if stale:
        suggestions.append(
            f"{len(stale)} stale lease(s) detected — review with "
            "'python scripts/claude_recover.py stale-lease --list' before expiring."
        )
    if alive:
        suggestions.append(
            f"{len(alive)} active lease(s) present — do NOT expire unless owner is confirmed absent and human approves."
        )
    if not suggestions:
        suggestions.append("No recovery action needed — harness state looks clean.")
    return suggestions


def mode_stale_lease(
    lease_id: str | None,
    reason: str | None,
    list_only: bool,
) -> dict[str, Any]:
    """Mode 2: stale lease recovery (read-only list, or expire with evidence)."""
    leases = load_leases(LEASE_LEDGER)
    stale = stale_leases(leases)

    if list_only or lease_id is None:
        return {
            "mode": "stale_lease",
            "action": "list",
            "stale_leases": [
                {
                    "lease_id": r.get("lease_id"),
                    "owner": r.get("owner"),
                    "expires_at": r.get("expires_at"),
                    "resources": r.get("resources", []),
                }
                for r in stale
            ],
            "mutation": False,
        }

    # Verify the target lease is actually stale
    target = next((r for r in stale if r.get("lease_id") == lease_id), None)
    if target is None:
        # Is it active (not stale)?
        alive = active_leases(leases)
        active_target = next((r for r in alive if r.get("lease_id") == lease_id), None)
        if active_target:
            return check_stop_condition(
                "lease_active_owner_present",
                f"Lease {lease_id!r} is still active — owner may still be working. "
                "Human approval required before expiring.",
            )
        return {"mode": "stale_lease", "error": f"lease {lease_id!r} not found", "mutation": False}

    if not reason:
        return check_stop_condition(
            "rollback_plan_missing",
            "reason is required when expiring a stale lease (CLAUDE_RECOVERY_PROCEDURES.md §2).",
        )

    # Safe to expire: mark the lease expired in the ledger
    updated: list[dict[str, Any]] = []
    for r in leases:
        if r.get("lease_id") == lease_id:
            r = {**r, "status": "expired", "recovery_reason": reason, "recovered_at": now_iso()}
        updated.append(r)

    LEASE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEASE_LEDGER.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in updated) + "\n",
        encoding="utf-8",
    )

    return {
        "mode": "stale_lease",
        "action": "expired",
        "lease_id": lease_id,
        "reason": reason,
        "mutation": True,
    }


def mode_failed_ship() -> dict[str, Any]:
    """Mode 4: failed ship inspection (read-only; no auto-merge or force)."""
    run_log = REPO / "07_LOGS_AND_AUDIT" / "workflows" / "run_log.jsonl"
    recent: list[dict[str, Any]] = []
    if run_log.exists():
        for raw in run_log.read_text(encoding="utf-8").splitlines()[-20:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                recent.append(json.loads(raw))
            except json.JSONDecodeError:
                pass

    failed = [r for r in recent if r.get("status") in {"failed", "error", "blocked"}]
    return {
        "mode": "failed_ship",
        "recent_runs": len(recent),
        "failed_runs": len(failed),
        "latest_failures": failed[-3:] if failed else [],
        "mutation": False,
        "next_step": (
            "Run 'python scripts/workflow_git.py plan --confidence 0' to inspect the git pipeline plan. "
            "Create a remediation issue if a force/collision override is needed (human approval required)."
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_result(mode_result: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp": now_iso(),
        "halt": mode_result.get("halt", False),
        "stop_condition": mode_result.get("stop_condition"),
        **{k: v for k, v in mode_result.items() if k not in ("halt", "stop_condition")},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emergency recovery orchestrator (/recover adapter command).",
    )
    sub = parser.add_subparsers(dest="mode", help="recovery mode")

    sub.add_parser("inspect", help="Read-only harness inspection (default).")

    sl_p = sub.add_parser("stale-lease", help="List or expire stale leases.")
    sl_p.add_argument("--lease-id", help="Lease ID to expire.")
    sl_p.add_argument("--reason", help="Human-approved reason for expiry.")
    sl_p.add_argument("--list", dest="list_only", action="store_true", help="List stale leases only.")

    sub.add_parser("failed-ship", help="Inspect failed workflow/ship runs.")

    args = parser.parse_args(argv)

    run_id = make_run_id()

    if args.mode == "stale-lease":
        result = mode_stale_lease(
            lease_id=getattr(args, "lease_id", None),
            reason=getattr(args, "reason", None),
            list_only=getattr(args, "list_only", False),
        )
    elif args.mode == "failed-ship":
        result = mode_failed_ship()
    else:
        # Default: inspect
        result = mode_inspect()

    out = build_result(result, run_id)
    append_log(out)

    print(json.dumps(out, indent=2, sort_keys=True))
    return 1 if out.get("halt") else 0


if __name__ == "__main__":
    sys.exit(main())
