#!/usr/bin/env python3
"""Run bounded bead hygiene governance cycles with optional Claude delegation.

This loop is intentionally bounded by --cycles. It can execute malformed-id review
annotations safely because those actions never auto-close issues.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO / ".agents" / "audits" / "bead_hygiene"


def _run(cmd: list[str], timeout: int = 300) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def _run_py(script: str, *args: str, timeout: int = 300) -> dict[str, Any]:
    return _run([sys.executable, str(REPO / script), *args], timeout=timeout)


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _malformed_targets(commands_json: Path) -> list[str]:
    data = _read_json(commands_json, {})
    rows = data.get("commands") if isinstance(data, dict) else []
    out: list[str] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("action_type") != "malformed_review":
            continue
        target = str(row.get("target_id") or "").strip()
        if target:
            out.append(target)
    return out


def _delegate_to_claude(
    task: str,
    bead_id: str,
    spawn: bool,
    *,
    run_id: str,
    task_id: str,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "claude_delegate_gate.py"),
        "--task",
        task,
        "--bead-id",
        bead_id,
        "--run-id",
        run_id,
        "--task-id",
        task_id,
        "--t-level",
        "T2",
        "--invoked-by",
        "automation",
    ]
    if spawn:
        cmd.append("--spawn-claude-cli")
    return _run(cmd, timeout=900)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded bead hygiene auto-loop")
    parser.add_argument("--cycles", type=int, default=3, help="Maximum cycles to run")
    parser.add_argument(
        "--bead-hygiene-active-duplicate-threshold",
        type=int,
        default=0,
        help="Threshold forwarded to daily_harness_audit strict runs",
    )
    parser.add_argument(
        "--max-malformed-per-cycle",
        type=int,
        default=0,
        help="Cap malformed_review actions per cycle (0 means all)",
    )
    parser.add_argument(
        "--execute-malformed",
        action="store_true",
        help="Execute malformed_review actions from remediation commands",
    )
    parser.add_argument(
        "--delegate-claude",
        action="store_true",
        help="Create Claude delegation packet when residual malformed IDs remain",
    )
    parser.add_argument(
        "--spawn-claude-cli",
        action="store_true",
        help="With --delegate-claude, also invoke claude CLI via delegation gate",
    )
    parser.add_argument(
        "--owner-bead-id",
        default="chromatic-harness-v2-4n4",
        help="Owner bead for delegation context",
    )
    parser.add_argument("extras", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Harden accidental placeholder args on Windows operators.
    ignored = [x for x in args.extras if x.strip() in {".", "./", ".\\"}]
    run_id = f"bhloop-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"

    started = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "audit": "bead_hygiene_autoloop",
        "run_id": run_id,
        "started": started,
        "cycles_requested": max(1, args.cycles),
        "ignored_extras": ignored,
        "cycles": [],
    }

    cycles = max(1, args.cycles)
    for idx in range(1, cycles + 1):
        task_id = f"{args.owner_bead_id}-delegation-c{idx}"
        cycle: dict[str, Any] = {"cycle": idx, "task_id": task_id, "steps": []}

        step1 = _run_py("scripts/bead_hygiene_audit.py", "--write", "--write-remediation-plan")
        cycle["steps"].append({"name": "bead_hygiene_audit", **step1})

        step2 = _run_py("scripts/bead_hygiene_remediation_commands.py", "--write")
        cycle["steps"].append({"name": "remediation_commands", **step2})

        commands_json = AUDIT_DIR / "latest_remediation_commands.json"
        targets = _malformed_targets(commands_json)
        selected = targets
        if args.max_malformed_per_cycle and args.max_malformed_per_cycle > 0:
            selected = targets[: args.max_malformed_per_cycle]

        applied: list[dict[str, Any]] = []
        if args.execute_malformed:
            for tid in selected:
                app = _run_py(
                    "scripts/bead_hygiene_apply_remediation.py",
                    "--execute",
                    "--target-id",
                    tid,
                    "--write",
                )
                applied.append({"target_id": tid, **app})
        cycle["malformed_targets"] = {
            "available": len(targets),
            "selected": len(selected),
            "applied": len(applied),
        }
        cycle["apply_steps"] = applied

        step3 = _run_py(
            "scripts/daily_harness_audit.py",
            "--root",
            ".",
            "--report",
            "--strict",
            "--bead-hygiene-active-duplicate-threshold",
            str(args.bead_hygiene_active_duplicate_threshold),
            timeout=900,
        )
        cycle["steps"].append({"name": "daily_harness_audit", **step3})

        latest = _read_json(AUDIT_DIR / "latest.json", {})
        findings = latest.get("findings") if isinstance(latest, dict) else []
        finding_counts = {
            str(f.get("code")): int(f.get("count") or 0)
            for f in findings
            if isinstance(f, dict) and f.get("code")
        }
        dup_active = int(finding_counts.get("duplicate_active_titles", 0) or 0)
        malformed = int(finding_counts.get("bead_id_hygiene_warning", 0) or 0)

        daily = _read_json(REPO / ".agents" / "audits" / "latest_audit.json", {})
        daily_status = (
            daily.get("daily_status")
            if isinstance(daily, dict)
            else None
        ) or (daily.get("status") if isinstance(daily, dict) else None)

        cycle["status"] = {
            "bead_hygiene_status": latest.get("status") if isinstance(latest, dict) else None,
            "daily_status": daily_status,
            "duplicate_active_titles": dup_active,
            "malformed_ids": malformed,
        }

        if args.delegate_claude and malformed > 0:
            task = (
                f"Continue malformed bead-id remediation planning/execution. "
                f"Current malformed count: {malformed}. "
                f"Maintain threshold {args.bead_hygiene_active_duplicate_threshold} and governance artifacts."
            )
            cycle["claude_delegate"] = _delegate_to_claude(
                task,
                args.owner_bead_id,
                args.spawn_claude_cli,
                run_id=run_id,
                task_id=task_id,
            )
            cycle["delegation_observability"] = _run_py(
                "scripts/claude_delegation_observability.py",
                "--write",
                "--bead-id",
                args.owner_bead_id,
                "--run-id",
                run_id,
                "--task-id",
                task_id,
            )

        summary["cycles"].append(cycle)

        if dup_active == 0 and malformed == 0:
            break

    summary["finished"] = datetime.now(timezone.utc).isoformat()
    summary["cycles_completed"] = len(summary["cycles"])

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / "latest_autoloop_report.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
