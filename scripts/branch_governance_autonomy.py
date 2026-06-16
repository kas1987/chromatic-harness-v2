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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
OUT_PATH = OUT_DIR / "branch_governance_autonomy_latest.json"
AUDIT_PATH = OUT_DIR / "branch_governance_latest.json"
CONFIG_PATH = REPO / "config" / "ci" / "branch_governance.yaml"


def _run(cmd: list[str], timeout: int = 240) -> dict[str, Any]:
    proc = run_safe(cmd, cwd=REPO, timeout=timeout)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-6000:],
        "ok": proc.returncode == 0,
    }


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


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

    primary = _run(cmd, timeout=420)
    if primary.get("ok"):
        return {"mode": "subagent", "result": primary, "fallback_used": False}

    out = (primary.get("stdout") or "") + "\n" + (primary.get("stderr") or "")
    if "pre_swarm_gate_failed" not in out:
        return {"mode": "subagent", "result": primary, "fallback_used": False}

    fallback_prompt = (
        "Autonomously remediate stale branch governance findings for chromatic-harness-v2. "
        f"Task level={t_level}. Preserve protected branches and produce a concise remediation report."
    )
    fallback = _run(["claude", "-p", fallback_prompt], timeout=420)
    return {
        "mode": "subagent",
        "result": primary,
        "fallback_used": True,
        "fallback": fallback,
    }


def _workflow_not_found(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    stderr = str(result.get("stderr") or "").lower()
    return (
        ("workflow" in stderr and "not found" in stderr)
        or ("could not find any workflows named" in stderr)
    )


def _mode_cloud(*, workflow: str, include_ci_weekly: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    attempted: list[str] = []

    candidates = [workflow]
    if workflow != "Branch Governance Weekly":
        candidates.append("Branch Governance Weekly")
    if workflow != "ci-governance-weekly.yml":
        candidates.append("ci-governance-weekly.yml")

    selected_ok = False
    for wf in candidates:
        if wf in attempted:
            continue
        attempted.append(wf)
        res = _run(["gh", "workflow", "run", wf], timeout=120)
        results.append(res)
        if res.get("ok"):
            selected_ok = True
            break
        if not _workflow_not_found(res):
            break

    if include_ci_weekly:
        ci_res = _run(["gh", "workflow", "run", "ci-governance-weekly.yml"], timeout=120)
        results.append(ci_res)

    ok = selected_ok and all(r.get("ok") for r in results[-1:] if r.get("cmd", [None, None, None])[-1] == "ci-governance-weekly.yml")
    if include_ci_weekly and len(results) >= 2:
        ok = selected_ok and bool(results[-1].get("ok"))
    elif not include_ci_weekly:
        ok = selected_ok
    return {"mode": "cloud", "ok": ok, "results": results, "attempted": attempted}


def main() -> int:
    cfg = _load_config()
    autonomy = cfg.get("autonomy") if isinstance(cfg.get("autonomy"), dict) else {}

    ap = argparse.ArgumentParser(description="Autonomous branch governance runner")
    ap.add_argument("--mode", choices=["local", "subagent", "cloud"], default=None)
    ap.add_argument("--apply", action="store_true", help="Apply local branch self-heal mutations")
    ap.add_argument("--spawn-subagent", action="store_true", help="Spawn Claude CLI for subagent mode")
    ap.add_argument("--t-level", choices=["T1", "T2", "T3", "T4"], default="T2")
    ap.add_argument("--cloud-workflow", default="branch-governance-weekly.yml")
    ap.add_argument("--include-ci-weekly", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    mode = args.mode or str(autonomy.get("mode") or "local")
    apply = args.apply or bool(autonomy.get("apply_mutations", False))

    if mode not in {"local", "subagent", "cloud"}:
        print(json.dumps({"error": f"unsupported mode: {mode}"}, indent=2))
        return 2

    if mode == "subagent" and not bool(autonomy.get("allow_subagent_mode", True)):
        print(json.dumps({"error": "subagent mode disabled by policy"}, indent=2))
        return 2

    if mode == "cloud" and not bool(autonomy.get("allow_cloud_mode", True)):
        print(json.dumps({"error": "cloud mode disabled by policy"}, indent=2))
        return 2

    if mode != "local" and apply:
        print(json.dumps({"error": "--apply is only valid with local mode"}, indent=2))
        return 2

    audit_refresh = _run([sys.executable, "scripts/branch_governance_audit.py", "--write"], timeout=300)

    if mode == "local":
        action = _mode_local(apply=apply)
    elif mode == "subagent":
        action = _mode_subagent(spawn=args.spawn_subagent, t_level=args.t_level)
    else:
        action = _mode_cloud(workflow=args.cloud_workflow, include_ci_weekly=args.include_ci_weekly)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "apply": apply,
        "audit_refresh": audit_refresh,
        "action": action,
    }

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))

    if not audit_refresh.get("ok"):
        return 1

    if mode == "cloud":
        return 0 if bool(action.get("ok")) else 1

    result = action.get("result") if isinstance(action, dict) else None
    if isinstance(result, dict):
        return 0 if result.get("ok") else result.get("returncode", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
