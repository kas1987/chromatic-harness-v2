#!/usr/bin/env python3
"""Closed-loop GO: score → self_heal → auto_intake → GO again.

Usage:
  python scripts/workflow_self_heal_cycle.py
  python scripts/workflow_self_heal_cycle.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

PYTHON = sys.executable


def _run_go() -> dict:
    proc = run_safe(
        [PYTHON, str(REPO / "scripts" / "workflow_go.py"), "GO"],
        cwd=REPO,
        timeout=120,
    )
    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        line = raw.split("\n")[-1] if raw else "{}"
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            data = {"error": "invalid_json", "raw": raw[:2000], "returncode": proc.returncode}
    data["_returncode"] = proc.returncode
    return data


def _run_auto_intake(limit: int) -> dict:
    proc = run_safe(
        [PYTHON, str(REPO / "scripts" / "auto_intake.py"), "--limit", str(limit)],
        cwd=REPO,
        timeout=180,
    )
    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"error": "invalid_json", "stderr": proc.stderr[:500]}
    data["_returncode"] = proc.returncode
    return data


def _run_branch_autonomy(mode: str, apply: bool) -> dict:
    cmd = [
        PYTHON,
        str(REPO / "scripts" / "branch_governance_autonomy.py"),
        "--mode",
        mode,
        "--write",
    ]
    if apply:
        cmd.append("--apply")
    proc = run_safe(cmd, cwd=REPO, timeout=300)
    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"error": "invalid_json", "stderr": (proc.stderr or "")[:500]}
    data["_returncode"] = proc.returncode
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-heal closed loop for workflow_go")
    parser.add_argument("--limit", type=int, default=10, help="auto_intake batch limit")
    parser.add_argument(
        "--branch-mode",
        choices=["off", "local", "subagent", "cloud"],
        default="local",
        help="branch governance self-heal execution mode during self_heal loop",
    )
    parser.add_argument(
        "--branch-apply",
        action="store_true",
        help="allow mutating branch cleanup actions when branch mode supports it",
    )
    args = parser.parse_args()

    first = _run_go()
    summary: dict = {
        "passes": [{"phase": "go_initial", "decision": first.get("decision"), "bead_id": first.get("bead_id")}],
        "intake": None,
        "final": first,
    }

    if first.get("decision") != "self_heal":
        summary["status"] = first.get("decision") or "unknown"
        summary["cycled"] = False
        print(json.dumps(summary, indent=2))
        return first.get("_returncode", 0) or 0

    intake = _run_auto_intake(args.limit)
    summary["intake"] = intake
    summary["passes"].append({"phase": "auto_intake", "processed": intake.get("processed")})

    if args.branch_mode != "off":
        branch = _run_branch_autonomy(args.branch_mode, args.branch_apply)
        summary["branch_autonomy"] = branch
        summary["passes"].append(
            {
                "phase": "branch_autonomy",
                "mode": args.branch_mode,
                "ok": branch.get("_returncode") == 0,
            }
        )

    second = _run_go()
    summary["passes"].append({"phase": "go_after_intake", "decision": second.get("decision")})
    summary["final"] = second
    summary["cycled"] = True
    summary["status"] = second.get("decision") or "unknown"

    print(json.dumps(summary, indent=2))
    rc = second.get("_returncode", 0)
    return 0 if rc is None else int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
