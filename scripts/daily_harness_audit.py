#!/usr/bin/env python3
"""Daily Chromatic Harness v2 audit aggregator.

Runs lightweight checks and writes repo-local audit reports.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CORE_FILES = [
    "AGENT_OPERATIONS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/governance/IDE_CLI_PARITY_POLICY.md",
    "docs/governance/DAILY_AUDIT_RUNBOOK.md",
]

CORE_SCRIPTS = [
    "scripts/new_session_bootstrap.py",
    "scripts/context_trim_audit.py",
    "scripts/context_rebuild.py",
    "scripts/daily_harness_audit.py",
    "scripts/audit_ide_parity.py",
    "scripts/audit_instruction_drift.py",
]

OPTIONAL_COMMANDS = [
    ["bd", "ready"],
    ["git", "status", "--short"],
]


def run_cmd(root: Path, cmd: list[str], timeout: int = 45) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "ok": proc.returncode == 0,
        }
    except FileNotFoundError as exc:
        return {"cmd": cmd, "returncode": None, "stdout": "", "stderr": str(exc), "ok": False, "missing": True}
    except subprocess.TimeoutExpired as exc:
        return {"cmd": cmd, "returncode": None, "stdout": exc.stdout or "", "stderr": "timeout", "ok": False, "timeout": True}


def severity_rank(sev: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(sev, 9)


def audit(root: Path, strict: bool = False, run_tests: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    findings: list[dict[str, Any]] = []

    for rel in CORE_FILES:
        if not (root / rel).exists():
            findings.append({"severity": "P1" if rel == "AGENT_OPERATIONS.md" else "P2", "code": "missing_core_file", "file": rel})

    for rel in CORE_SCRIPTS:
        if not (root / rel).exists():
            findings.append({"severity": "P1", "code": "missing_core_script", "file": rel})

    command_results: list[dict[str, Any]] = []
    for cmd in OPTIONAL_COMMANDS:
        command_results.append(run_cmd(root, cmd))

    # Run local audit scripts if available.
    for script in ["scripts/audit_ide_parity.py", "scripts/audit_instruction_drift.py"]:
        if (root / script).exists():
            result = run_cmd(root, ["python", script, "--root", str(root)])
            command_results.append(result)
            if result["stdout"]:
                try:
                    parsed = json.loads(result["stdout"])
                    findings.extend(parsed.get("findings", []))
                except Exception:
                    findings.append({"severity": "P3", "code": "audit_parse_warning", "file": script})

    # Optional pre-session/context scripts. Warnings only if missing, because packs may be installed incrementally.
    optional_scripts = [
        "scripts/new_session_bootstrap.py",
        "scripts/context_trim_audit.py",
        "scripts/generate_pre_session_inventory.py",
        "scripts/audit_mcp_context.py",
        "scripts/check_agent_operations.py",
        "scripts/validate_instruction_governance.py",
        "scripts/validate_governance_stack.py",
        "scripts/validate_intake_loop.py",
    ]
    for script in optional_scripts:
        if (root / script).exists():
            args = ["python", script]
            if script.endswith("audit_mcp_context.py"):
                args += ["--profile", "harness_dev"]
            elif script.endswith("check_agent_operations.py"):
                pass
            elif script.endswith("validate_governance_stack.py") or script.endswith(
                "validate_instruction_governance.py"
            ) or script.endswith("validate_intake_loop.py"):
                pass
            else:
                args += ["--root", str(root)]
            command_results.append(run_cmd(root, args))
        else:
            findings.append({"severity": "P2", "code": "optional_audit_script_missing", "file": script})

    if run_tests and (root / "tests").exists():
        command_results.append(run_cmd(root, ["pytest", "tests", "-q"], timeout=120))

    counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for f in findings:
        counts[f.get("severity", "P3")] = counts.get(f.get("severity", "P3"), 0) + 1

    if counts["P0"] or counts["P1"]:
        status = "red" if strict else "yellow"
    elif counts["P2"]:
        status = "yellow"
    else:
        status = "green"

    return {
        "audit": "daily_harness_audit",
        "timestamp": now,
        "root": str(root),
        "strict": strict,
        "status": status,
        "counts": counts,
        "findings": sorted(findings, key=lambda f: severity_rank(f.get("severity", "P3"))),
        "commands": command_results,
    }


def write_reports(root: Path, result: dict[str, Any]) -> None:
    out = root / ".agents" / "audits"
    daily = out / "daily"
    findings_dir = out / "findings"
    daily.mkdir(parents=True, exist_ok=True)
    findings_dir.mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime("%Y-%m-%d")
    (out / "latest_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Latest Harness Audit Summary",
        "",
        f"Status: **{result['status'].upper()}**",
        f"Timestamp: `{result['timestamp']}`",
        "",
        "## Finding Counts",
        "",
        "| Severity | Count |",
        "|---|---:|",
    ]
    for sev in ["P0", "P1", "P2", "P3"]:
        lines.append(f"| {sev} | {result['counts'].get(sev, 0)} |")
    lines += ["", "## Findings", ""]
    if result["findings"]:
        for f in result["findings"]:
            lines.append(f"- **{f.get('severity','P3')}** `{f.get('code','unknown')}` {f.get('file','')} {f.get('message','')}")
    else:
        lines.append("No findings.")
    lines.append("")

    summary = "\n".join(lines)
    (out / "latest_audit_summary.md").write_text(summary, encoding="utf-8")
    (daily / f"{date}_AUDIT_REPORT.md").write_text(summary, encoding="utf-8")

    with (findings_dir / "open_findings.jsonl").open("w", encoding="utf-8") as fh:
        for f in result["findings"]:
            fh.write(json.dumps(f) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = audit(root, strict=args.strict, run_tests=args.run_tests)
    if args.report:
        write_reports(root, result)
    print(json.dumps(result, indent=2))
    return 1 if args.strict and result["status"] == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
