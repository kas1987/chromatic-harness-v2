#!/usr/bin/env python3
"""Daily Chromatic Harness v2 audit aggregator.

Runs lightweight checks and writes repo-local audit reports.
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

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from intake.bd_runner import resolve_bd_argv  # noqa: E402

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


def _resolve_cmd(cmd: list[str]) -> list[str]:
    if cmd and cmd[0] == "bd":
        return resolve_bd_argv() + cmd[1:]
    return cmd


def run_cmd(root: Path, cmd: list[str], timeout: int = 45) -> dict[str, Any]:
    cmd = _resolve_cmd(cmd)
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "ok": proc.returncode == 0,
        }
    except FileNotFoundError as exc:
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "ok": False,
            "missing": True,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": "timeout",
            "ok": False,
            "timeout": True,
        }


def severity_rank(sev: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(sev, 9)


def audit(
    root: Path,
    strict: bool = False,
    run_tests: bool = False,
    lock_timeout_rate_threshold: float = 0.05,
    lock_wait_p95_threshold_ms: int = 500,
    lock_min_sample_size: int = 20,
    bead_hygiene_active_duplicate_threshold: int = 0,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    findings: list[dict[str, Any]] = []
    lock_metrics_summary: dict[str, Any] = {}
    bead_hygiene_summary: dict[str, Any] = {}

    for rel in CORE_FILES:
        if not (root / rel).exists():
            findings.append(
                {
                    "severity": "P1" if rel == "AGENT_OPERATIONS.md" else "P2",
                    "code": "missing_core_file",
                    "file": rel,
                }
            )

    for rel in CORE_SCRIPTS:
        if not (root / rel).exists():
            findings.append(
                {"severity": "P1", "code": "missing_core_script", "file": rel}
            )

    command_results: list[dict[str, Any]] = []
    for cmd in OPTIONAL_COMMANDS:
        command_results.append(run_cmd(root, cmd))

    # Run local audit scripts if available.
    for script in [
        "scripts/audit_ide_parity.py",
        "scripts/audit_instruction_drift.py",
        "scripts/validate_claude_harness.py",
    ]:
        if (root / script).exists():
            result = run_cmd(root, ["python", script, "--root", str(root)])
            command_results.append(result)
            if not result.get("ok") and script.endswith("validate_claude_harness.py"):
                findings.append(
                    {
                        "severity": "P1",
                        "code": "claude_harness_not_production_ready",
                        "file": script,
                        "message": (result.get("stderr") or result.get("stdout") or "")[
                            :400
                        ],
                    }
                )
            elif result["stdout"]:
                try:
                    parsed = json.loads(result["stdout"])
                    findings.extend(parsed.get("findings", []))
                except Exception:
                    if not script.endswith("validate_claude_harness.py"):
                        findings.append(
                            {
                                "severity": "P3",
                                "code": "audit_parse_warning",
                                "file": script,
                            }
                        )

    # Optional pre-session/context scripts. Warnings only if missing, because packs may be installed incrementally.
    optional_scripts = [
        "scripts/new_session_bootstrap.py",
        "scripts/context_trim_audit.py",
        "scripts/generate_pre_session_inventory.py",
        "scripts/audit_mcp_context.py",
        "scripts/llm_governance_intelligence.py",
        "scripts/bead_hygiene_audit.py",
        "scripts/bead_hygiene_remediation_commands.py",
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
            elif script.endswith("llm_governance_intelligence.py"):
                # Script does not accept --root; run with defaults for quick telemetry health.
                pass
            elif script.endswith("bead_hygiene_audit.py"):
                args += ["--write", "--write-remediation-plan"]
            elif script.endswith("bead_hygiene_remediation_commands.py"):
                args += ["--write"]
            elif script.endswith("check_agent_operations.py"):
                pass
            elif script.endswith("generate_pre_session_inventory.py"):
                pass
            elif (
                script.endswith("validate_governance_stack.py")
                or script.endswith("validate_instruction_governance.py")
                or script.endswith("validate_intake_loop.py")
            ):
                pass
            else:
                args += ["--root", str(root)]
            result = run_cmd(root, args)
            command_results.append(result)
            if script.endswith("bead_hygiene_audit.py"):
                hygiene_path = (
                    root / ".agents" / "audits" / "bead_hygiene" / "latest.json"
                )
                try:
                    payload = (
                        json.loads(hygiene_path.read_text(encoding="utf-8"))
                        if hygiene_path.is_file()
                        else json.loads(result.get("stdout") or "{}")
                    )
                except Exception:
                    payload = {}
                hygiene_status = str(payload.get("status") or "").lower()
                active_duplicate_count = 0
                for item in payload.get("findings") or []:
                    if (
                        isinstance(item, dict)
                        and item.get("code") == "duplicate_active_titles"
                    ):
                        active_duplicate_count = int(item.get("count") or 0)
                        break

                bead_hygiene_summary = {
                    "status": hygiene_status or "unknown",
                    "active_duplicate_count": active_duplicate_count,
                    "active_duplicate_threshold": bead_hygiene_active_duplicate_threshold,
                }

                if hygiene_status == "red":
                    if (
                        active_duplicate_count
                        <= bead_hygiene_active_duplicate_threshold
                    ):
                        findings.append(
                            {
                                "severity": "P2",
                                "code": "bead_hygiene_red_below_threshold",
                                "file": script,
                                "message": (
                                    "bead hygiene RED downgraded by threshold gate: "
                                    f"active_duplicates={active_duplicate_count} "
                                    f"<= threshold={bead_hygiene_active_duplicate_threshold}"
                                ),
                            }
                        )
                    else:
                        findings.append(
                            {
                                "severity": "P1",
                                "code": "bead_hygiene_red",
                                "file": script,
                                "message": (
                                    "bead hygiene audit reported RED status; "
                                    f"active_duplicates={active_duplicate_count} "
                                    f"> threshold={bead_hygiene_active_duplicate_threshold}; "
                                    "review remediation plan"
                                ),
                            }
                        )
                elif hygiene_status == "yellow":
                    findings.append(
                        {
                            "severity": "P2",
                            "code": "bead_hygiene_yellow",
                            "file": script,
                            "message": "bead hygiene audit reported YELLOW status",
                        }
                    )
        else:
            findings.append(
                {
                    "severity": "P2",
                    "code": "optional_audit_script_missing",
                    "file": script,
                }
            )

    if run_tests and (root / "tests").exists():
        command_results.append(run_cmd(root, ["pytest", "tests", "-q"], timeout=120))

    pre_session = root / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"
    if pre_session.is_file():
        try:
            ps = json.loads(pre_session.read_text(encoding="utf-8"))
            mcp = ps.get("mcp_audit") or {}
            if mcp.get("over_warn_threshold"):
                findings.append(
                    {
                        "severity": "P1",
                        "code": "mcp_token_budget_exceeded",
                        "file": str(pre_session.relative_to(root)),
                        "message": (
                            f"MCP estimated tokens {mcp.get('estimated_tokens_if_enabled')} "
                            f"exceeds warn threshold {mcp.get('warn_threshold')}; "
                            "disable heavy MCPs per docs/CURSOR_CONTEXT_HYGIENE.md"
                        ),
                    }
                )
        except (json.JSONDecodeError, OSError):
            pass

    rollup_script = root / "scripts" / "lock_metrics_rollup.py"
    if rollup_script.is_file():
        rollup_cmd = ["python", str(rollup_script), "--lookback-days", "7", "--write"]
        rollup_result = run_cmd(root, rollup_cmd)
        command_results.append(rollup_result)
        if rollup_result.get("ok") and rollup_result.get("stdout"):
            try:
                lock_rollup = json.loads(rollup_result["stdout"])
                timeout_rate = float(lock_rollup.get("timeout_rate", 0.0))
                wait_p95 = int((lock_rollup.get("wait_ms") or {}).get("p95", 0))
                total_events = int(
                    (lock_rollup.get("event_counts") or {}).get("total", 0)
                )
                lock_metrics_summary = {
                    "timeout_rate": timeout_rate,
                    "wait_p95_ms": wait_p95,
                    "total_events": total_events,
                    "threshold_timeout_rate": lock_timeout_rate_threshold,
                    "threshold_wait_p95_ms": lock_wait_p95_threshold_ms,
                    "min_sample_size": lock_min_sample_size,
                }
                if timeout_rate > lock_timeout_rate_threshold:
                    severity = "P1" if total_events >= lock_min_sample_size else "P2"
                    code = (
                        "lock_timeout_rate_high"
                        if total_events >= lock_min_sample_size
                        else "lock_timeout_rate_high_low_sample"
                    )
                    findings.append(
                        {
                            "severity": severity,
                            "code": code,
                            "file": "docs/workflows/WORKFLOW_RUN_LOG.jsonl",
                            "message": (
                                f"lock timeout_rate={timeout_rate} exceeds threshold="
                                f"{lock_timeout_rate_threshold}; sample_size={total_events}"
                            ),
                        }
                    )
                if wait_p95 > lock_wait_p95_threshold_ms:
                    findings.append(
                        {
                            "severity": "P2",
                            "code": "lock_wait_p95_high",
                            "file": "docs/workflows/WORKFLOW_RUN_LOG.jsonl",
                            "message": (
                                f"lock wait p95={wait_p95}ms exceeds threshold="
                                f"{lock_wait_p95_threshold_ms}ms"
                            ),
                        }
                    )
            except (ValueError, json.JSONDecodeError):
                findings.append(
                    {
                        "severity": "P3",
                        "code": "lock_metrics_parse_warning",
                        "file": "scripts/lock_metrics_rollup.py",
                    }
                )

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
        "lock_metrics": lock_metrics_summary,
        "bead_hygiene": bead_hygiene_summary,
        "findings": sorted(
            findings, key=lambda f: severity_rank(f.get("severity", "P3"))
        ),
        "commands": command_results,
    }


def write_reports(root: Path, result: dict[str, Any]) -> None:
    out = root / ".agents" / "audits"
    daily = out / "daily"
    findings_dir = out / "findings"
    daily.mkdir(parents=True, exist_ok=True)
    findings_dir.mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime("%Y-%m-%d")
    (out / "latest_audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

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
            lines.append(
                f"- **{f.get('severity', 'P3')}** `{f.get('code', 'unknown')}` {f.get('file', '')} {f.get('message', '')}"
            )
    else:
        lines.append("No findings.")
    lock_metrics = result.get("lock_metrics") or {}
    if lock_metrics:
        lines += [
            "",
            "## Lock Metrics",
            "",
            f"- Timeout rate: {lock_metrics.get('timeout_rate', 0.0)}",
            f"- Wait p95 (ms): {lock_metrics.get('wait_p95_ms', 0)}",
            f"- Total events: {lock_metrics.get('total_events', 0)}",
            f"- Timeout threshold: {lock_metrics.get('threshold_timeout_rate', 0.0)}",
            f"- Min sample size: {lock_metrics.get('min_sample_size', 0)}",
        ]
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
    parser.add_argument(
        "--lock-timeout-rate-threshold",
        type=float,
        default=float(os.environ.get("CHROMATIC_LOCK_TIMEOUT_RATE_THRESHOLD", "0.05")),
    )
    parser.add_argument(
        "--lock-wait-p95-threshold-ms",
        type=int,
        default=int(os.environ.get("CHROMATIC_LOCK_WAIT_P95_THRESHOLD_MS", "1500")),
    )
    parser.add_argument(
        "--lock-min-sample-size",
        type=int,
        default=int(os.environ.get("CHROMATIC_LOCK_MIN_SAMPLE_SIZE", "20")),
    )
    parser.add_argument(
        "--bead-hygiene-active-duplicate-threshold",
        type=int,
        default=int(
            os.environ.get("CHROMATIC_BEAD_HYGIENE_ACTIVE_DUPLICATE_THRESHOLD", "0")
        ),
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = audit(
        root,
        strict=args.strict,
        run_tests=args.run_tests,
        lock_timeout_rate_threshold=args.lock_timeout_rate_threshold,
        lock_wait_p95_threshold_ms=args.lock_wait_p95_threshold_ms,
        lock_min_sample_size=args.lock_min_sample_size,
        bead_hygiene_active_duplicate_threshold=args.bead_hygiene_active_duplicate_threshold,
    )
    write_reports(root, result)
    if not args.report:
        # Keep JSON on stdout for piping; summary still written for agents reading .agents/audits/
        pass
    print(json.dumps(result, indent=2))
    return 1 if args.strict and result["status"] == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
