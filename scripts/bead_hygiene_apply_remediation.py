#!/usr/bin/env python3
"""Apply bead hygiene remediation commands with explicit safety controls.

Default mode is dry-run. Execution requires both --execute and explicit --target-id values.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "02_RUNTIME"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(REPO / "scripts"))

from common_harness import run_safe  # noqa: E402
from intake.bd_runner import resolve_bd_argv  # noqa: E402

AUDIT_DIR = REPO / ".agents" / "audits" / "bead_hygiene"


def _run_bd(args: list[str]):
    cmd = [*resolve_bd_argv(), *args]
    return run_safe(cmd, cwd=REPO, timeout=120)


def _load_commands(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("commands") if isinstance(data, dict) else None
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def _apply_one(item: dict[str, Any], execute: bool) -> dict[str, Any]:
    action_type = str(item.get("action_type") or "duplicate_close")
    target_id = str(item.get("target_id") or "")
    canonical_id = str(item.get("canonical_id") or "")
    title = str(item.get("title") or "")
    reason = f"duplicate of {canonical_id}: {title}"[:160]

    if action_type == "malformed_review":
        comment_args = [
            "update",
            target_id,
            "--notes",
            "id-hygiene-review: non-canonical bead id; migrate to canonical id",
        ]
        close_args: list[str] = []
    else:
        comment_args = ["update", target_id, "--notes", f"duplicate-triage: merged into {canonical_id}"]
        close_args = ["close", target_id, "--reason", reason]

    out: dict[str, Any] = {
        "action_type": action_type,
        "target_id": target_id,
        "canonical_id": canonical_id,
        "comment_cmd": " ".join(["bd", *comment_args]),
        "close_cmd": " ".join(["bd", *close_args]) if close_args else "",
        "executed": execute,
        "ok": True,
        "steps": [],
    }

    if not execute:
        out["steps"].append({"name": "comment", "status": "dry-run"})
        if close_args:
            out["steps"].append({"name": "close", "status": "dry-run"})
        return out

    comment_proc = _run_bd(comment_args)
    out["steps"].append(
        {
            "name": "comment",
            "returncode": comment_proc.returncode,
            "stdout": (comment_proc.stdout or "")[-500:],
            "stderr": (comment_proc.stderr or "")[-500:],
            "ok": comment_proc.returncode == 0,
        }
    )
    if comment_proc.returncode != 0:
        out["ok"] = False
        return out

    if not close_args:
        return out

    close_proc = _run_bd(close_args)
    out["steps"].append(
        {
            "name": "close",
            "returncode": close_proc.returncode,
            "stdout": (close_proc.stdout or "")[-500:],
            "stderr": (close_proc.stderr or "")[-500:],
            "ok": close_proc.returncode == 0,
        }
    )
    if close_proc.returncode != 0:
        out["ok"] = False
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply bead hygiene remediation commands in controlled batches")
    parser.add_argument(
        "--commands",
        default=str(AUDIT_DIR / "latest_remediation_commands.json"),
        help="Path to remediation commands JSON",
    )
    parser.add_argument(
        "--target-id",
        action="append",
        default=[],
        help="Target bead id to apply (repeatable). Required for --execute.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of selected targets to process (0 means all selected).",
    )
    parser.add_argument("--execute", action="store_true", help="Actually execute bd update/bd close")
    parser.add_argument("--write", action="store_true", help="Write apply report artifact")
    args = parser.parse_args()

    commands_path = Path(args.commands)
    if not commands_path.is_absolute():
        commands_path = (REPO / commands_path).resolve()
    if not commands_path.is_file():
        raise SystemExit(f"missing commands file: {commands_path}")

    rows = _load_commands(commands_path)
    selected_ids = {tid.strip() for tid in args.target_id if tid.strip()}

    if args.execute and not selected_ids:
        raise SystemExit("--execute requires at least one --target-id")

    if selected_ids:
        rows = [r for r in rows if str(r.get("target_id") or "") in selected_ids]

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    results = [_apply_one(item, execute=args.execute) for item in rows]

    report = {
        "audit": "bead_hygiene_apply_remediation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execute": args.execute,
        "selected_targets": sorted(selected_ids),
        "processed": len(results),
        "ok": all(r.get("ok") for r in results),
        "results": results,
    }

    if args.write:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        (AUDIT_DIR / "latest_apply_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
