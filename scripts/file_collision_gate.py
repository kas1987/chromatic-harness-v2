#!/usr/bin/env python3
"""file_collision_gate.py — file-scope collision detection (P0-CC-004 / ju0o.4).

Before any autonomous write, agents call this gate to verify no other active
write/exclusive lease covers an overlapping path.  Read-only leases never block
writes (per DoD: "read-only leases do not block writes unless configured").

Wraps lease_manager.py — no new state format; reuses the active_leases ledger.

Usage:
    python scripts/file_collision_gate.py check --paths scripts/foo.py scripts/bar.py
    python scripts/file_collision_gate.py check --paths scripts/ --agent MyAgent
    python scripts/file_collision_gate.py list-blocked
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import lease_manager as _lm  # noqa: E402

DEFAULT_LEDGER = _lm.DEFAULT_LEDGER


def _normalise(path: str) -> str:
    """Normalise a filesystem path to a forward-slash resource identifier."""
    return path.replace("\\", "/").rstrip("/")


def check_write(
    paths: list[str],
    agent_id: str = "unknown",
    ledger: Path | None = None,
    allow_read_block: bool = False,
) -> dict[str, Any]:
    """Check whether *paths* can be written without colliding with active leases.

    By default, read-mode leases are skipped (they do not block writes).
    Set *allow_read_block=True* to treat read leases as blockers (opt-in per DoD).

    Returns:
        {"status": "safe",    "paths": [...], "agent_id": ...}  — no conflicts
        {"status": "blocked", "paths": [...], "conflicts": [...]}  — blocked
    """
    ledger = ledger or DEFAULT_LEDGER
    records = _lm.load_ledger(ledger)
    normalised = [_normalise(p) for p in paths]

    conflicts: list[dict[str, Any]] = []
    for record in records:
        if not _lm.is_active(record):
            continue
        # Skip read-mode leases unless opt-in blocking is requested.
        if not allow_read_block and record.get("mode") == "read":
            continue
        for existing in record.get("resources", []):
            existing_n = _normalise(existing)
            for req in normalised:
                if _lm.overlaps(existing_n, req):
                    conflicts.append(
                        {
                            "path": req,
                            "blocking_lease": record.get("lease_id"),
                            "blocking_agent": record.get("owner_agent"),
                            "blocking_mode": record.get("mode"),
                            "blocking_resource": existing,
                        }
                    )
                    break  # one match per record is enough

    if conflicts:
        return {
            "status": "blocked",
            "paths": normalised,
            "agent_id": agent_id,
            "conflicts": conflicts,
        }
    return {"status": "safe", "paths": normalised, "agent_id": agent_id, "conflicts": []}


def list_blocked_paths(ledger: Path | None = None) -> list[dict[str, Any]]:
    """Return all resources currently covered by active write/exclusive leases."""
    ledger = ledger or DEFAULT_LEDGER
    records = _lm.load_ledger(ledger)
    blocked: list[dict[str, Any]] = []
    for record in records:
        if not _lm.is_active(record):
            continue
        if record.get("mode") == "read":
            continue
        for resource in record.get("resources", []):
            blocked.append(
                {
                    "resource": resource,
                    "lease_id": record.get("lease_id"),
                    "owner_agent": record.get("owner_agent"),
                    "mode": record.get("mode"),
                    "expires_at": record.get("expires_at"),
                }
            )
    return blocked


ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "collision"
ARTIFACT_PATH = ARTIFACT_DIR / "file_collision_latest.json"


def summarize(ledger: Path | None = None) -> dict[str, Any]:
    """Fail-open summary for the harness health dashboard + artifact write."""
    try:
        blocked = list_blocked_paths(ledger)
        result = {
            "status": "ok",
            "blocked_path_count": len(blocked),
            "blocked": blocked,
        }
    except Exception as exc:  # noqa: BLE001
        result = {"status": "error", "error": str(exc), "blocked_path_count": None}
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="File-scope collision detection (P0-CC-004)")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check")
    p.add_argument("--paths", nargs="+", required=True, metavar="PATH")
    p.add_argument("--agent", default="unknown")
    p.add_argument("--allow-read-block", action="store_true", help="Treat read leases as blockers")

    sub.add_parser("list-blocked")
    sub.add_parser("summarize")

    args = parser.parse_args()
    ledger = Path(args.ledger)

    if args.command == "check":
        result = check_write(args.paths, args.agent, ledger, getattr(args, "allow_read_block", False))
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "safe" else 2

    if args.command == "list-blocked":
        print(json.dumps(list_blocked_paths(ledger), indent=2))
        return 0

    if args.command == "summarize":
        print(json.dumps(summarize(ledger), indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
