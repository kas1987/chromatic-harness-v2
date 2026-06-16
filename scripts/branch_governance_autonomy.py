#!/usr/bin/env python3
"""Autonomous branch-governance runner with local/subagent/cloud modes.

Modes:
- local: run local branch self-heal via branch_governance_enforce.py
- subagent: delegate branch remediation to local Claude via delegate gate
- cloud: dispatch GitHub workflows for branch governance checks/remediation
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
OUT_PATH = OUT_DIR / "branch_governance_autonomy_latest.json"
AUDIT_PATH = OUT_DIR / "branch_governance_latest.json"


def _run(cmd: list[str], timeout: int = 240) -> dict[str, Any]:
    proc = run_safe(cmd, cwd=REPO, timeout=timeout)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-6000:],
        "ok": proc.returncode == 0,
    }


def _load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.exists():
        return {}
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _mode_local(*, apply: bool) -> dict[str, Any]:
    args = [sys.executable, "scripts/branch_governance_enforce.py", "--write"]
    if apply:
        args.append("--apply")
    return {"mode": "local", "result": _run(args, timeout=300)}


def _mode_subagent(*, spawn: bool, t_level: str) -> dict[str, Any]:
    audit = _load_audit()
    counts = audit.get("counts") or {}
    local_stale = counts.get("local_stale", 0)
    remote_stale = counts.get("remote_stale", 0)
    task = (
        "Autonomously remediate stale branch governance findings in chromatic-harness-v2. "
        f"Current stale counts: local={local_stale}, remote={remote_stale}. "
        "Use branch governance policy, preserve protected branches, and provide a concise remediation report."
    )

    cmd = [
        sys.executable,
        "scripts/claude_delegate_gate.py",
        "--task",
        task,
        "--t-level",
        t_level,
        "--privacy-class",
        "P1",
    ]
    if spawn:
        cmd.append("--spawn-claude-cli")

    return {"mode": "subagent", "result": _run(cmd, timeout=420)}


def _mode_cloud(*, workflow: str, include_ci_weekly: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    cmd = ["gh", "workflow", "run", workflow]
    results.append(_run(cmd, timeout=120))

    if include_ci_weekly:
        results.append(_run(["gh", "workflow", "run", "ci-governance-weekly.yml"], timeout=120))

    ok = all(r.get("ok") for r in results)
    return {"mode": "cloud", "ok": ok, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser(description="Autonomous branch governance runner")
    ap.add_argument("--mode", choices=["local", "subagent", "cloud"], default="local")
    ap.add_argument("--apply", action="store_true", help="Apply local branch self-heal mutations")
    ap.add_argument("--spawn-subagent", action="store_true", help="Spawn Claude CLI for subagent mode")
    ap.add_argument("--t-level", choices=["T1", "T2", "T3", "T4"], default="T2")
    ap.add_argument("--cloud-workflow", default="branch-governance-weekly.yml")
    ap.add_argument("--include-ci-weekly", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    audit_refresh = _run([sys.executable, "scripts/branch_governance_audit.py", "--write"], timeout=300)

    if args.mode == "local":
        action = _mode_local(apply=args.apply)
    elif args.mode == "subagent":
        action = _mode_subagent(spawn=args.spawn_subagent, t_level=args.t_level)
    else:
        action = _mode_cloud(workflow=args.cloud_workflow, include_ci_weekly=args.include_ci_weekly)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "audit_refresh": audit_refresh,
        "action": action,
    }

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))

    if not audit_refresh.get("ok"):
        return 1

    if args.mode == "cloud":
        return 0 if bool(action.get("ok")) else 1

    result = action.get("result") if isinstance(action, dict) else None
    if isinstance(result, dict):
        return 0 if result.get("ok") else result.get("returncode", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
