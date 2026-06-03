#!/usr/bin/env python3
"""Token-governance closed loop: log, analyze, validate, and suggest follow-ups.

This script runs token-related audits, classifies pass/warn/fail outcomes,
logs a structured report, and optionally enqueues suggestion items into the
intake queue so they can become beads via auto_intake.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "02_RUNTIME"
for _p in (REPO, RUNTIME, REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from common_harness import run_safe  # noqa: E402
from intake.queue import append_entry, list_entries  # noqa: E402


@dataclass
class CheckResult:
    name: str
    command: list[str]
    status: str  # pass|warn|fail
    returncode: int
    message: str
    data: dict[str, Any]


def _run(command: list[str], timeout: int = 600) -> tuple[int, str, str]:
    proc = run_safe(command, cwd=REPO, timeout=timeout)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _parse_json(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _check_session_context() -> CheckResult:
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "session_context_report.py"),
        "--json",
        "--log",
        "--invoked-by",
        "harness",
    ]
    code, out, err = _run(cmd, timeout=180)
    data = _parse_json(out) or {}
    warnings = (data.get("summary") or {}).get("warnings") or []
    if code != 0:
        return CheckResult(
            "session_context_report",
            cmd,
            "fail",
            code,
            err.strip() or "command failed",
            data,
        )
    if warnings:
        return CheckResult("session_context_report", cmd, "warn", code, "; ".join(warnings), data)
    return CheckResult("session_context_report", cmd, "pass", code, "no warnings", data)


def _check_mcp_audit(profile: str) -> CheckResult:
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "audit_mcp_context.py"),
        "--profile",
        profile,
        "--json",
    ]
    code, out, err = _run(cmd, timeout=120)
    data = _parse_json(out) or {}
    if code != 0:
        return CheckResult(
            "audit_mcp_context",
            cmd,
            "fail",
            code,
            err.strip() or "command failed",
            data,
        )

    total = int(data.get("total_tokens_est", 0))
    warn = int(data.get("warn_threshold_tokens", 12000))
    heavy = data.get("heavy_servers_on_disk") or []
    if total > warn:
        return CheckResult(
            "audit_mcp_context",
            cmd,
            "warn",
            code,
            f"MCP tokens {total} exceed warn threshold {warn}",
            data,
        )
    if heavy:
        return CheckResult(
            "audit_mcp_context",
            cmd,
            "warn",
            code,
            f"Heavy MCP servers still present on disk: {', '.join(heavy)}",
            data,
        )
    return CheckResult("audit_mcp_context", cmd, "pass", code, "within threshold", data)


def _check_workflow_token_governance() -> CheckResult:
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "validate_workflow_token_governance.py"),
    ]
    code, out, err = _run(cmd, timeout=120)
    msg = (err or out).strip()
    if code != 0:
        return CheckResult("validate_workflow_token_governance", cmd, "fail", code, msg or "failed", {})
    return CheckResult(
        "validate_workflow_token_governance",
        cmd,
        "pass",
        code,
        "workflow token governance OK",
        {},
    )


def _check_daily_strict() -> CheckResult:
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "daily_harness_audit.py"),
        "--root",
        str(REPO),
        "--report",
        "--strict",
    ]
    code, out, err = _run(cmd, timeout=240)
    data = _parse_json(out) or {}
    status = str(data.get("status", "unknown"))
    if code != 0:
        return CheckResult(
            "daily_harness_audit_strict",
            cmd,
            "fail",
            code,
            err.strip() or f"status={status}",
            data,
        )
    if status != "green":
        return CheckResult("daily_harness_audit_strict", cmd, "warn", code, f"status={status}", data)
    return CheckResult("daily_harness_audit_strict", cmd, "pass", code, "status=green", data)


def _refresh_step(name: str, fn) -> dict[str, Any]:
    """Run one control-plane refresh step fail-open, capturing status + detail.

    Each step never raises: on exception it records status="fail" and the
    error message, so the periodic chain always advances to the next step
    (spec §10: never block the API path; staleness/down is non-fatal).
    """
    started = datetime.now(timezone.utc).isoformat()
    try:
        detail = fn() or {}
        return {
            "name": name,
            "status": "ok",
            "started_at": started,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001 — fail-open by design
        return {
            "name": name,
            "status": "fail",
            "started_at": started,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _refresh_control_plane() -> list[dict[str, Any]]:
    """Chain the full periodic refresh (spec §4–§8, bead B9).

    quota_proxy read -> portfolio_token_telemetry (post ledger) ->
    portfolio_token_forecast (axis_prepaid) -> controller (overlay) ->
    token_economy_exporter (metrics).

    Reuses existing component entry points in-process; does NOT rebuild
    aggregation. Every step is fail-open and logged independently so a
    stale/down proxy or a missing artifact degrades gracefully.
    """
    import importlib

    steps: list[dict[str, Any]] = []

    # 1. Capture layer — read the verified weekly % from quota_state.json
    #    (source-abstracted reader; the proxy is the long-running producer).
    def _read_quota() -> dict[str, Any]:
        quota_state = importlib.import_module("budget.quota_state")
        state = quota_state.read_quota_state()
        return {
            "weekly_pct": getattr(state, "weekly_pct", None),
            "stale": getattr(state, "stale", None),
            "status": getattr(state, "status", None),
        }

    steps.append(_refresh_step("quota_proxy_read", _read_quota))

    # 2. Posting engine — bridge today->daily, build + post ledger.jsonl.
    def _post_ledger() -> dict[str, Any]:
        telemetry = importlib.import_module("tools.portfolio_token_telemetry")
        return telemetry.run()

    steps.append(_refresh_step("portfolio_token_telemetry", _post_ledger))

    # 3. Forecast layer — extend forecast_latest.json with axis_prepaid.
    def _forecast() -> dict[str, Any]:
        forecast = importlib.import_module("tools.portfolio_token_forecast")
        report = forecast.build_report()
        out = forecast.DEFAULT_OUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return {
            "out": str(out),
            "axis_prepaid": report.get("axis_prepaid"),
        }

    steps.append(_refresh_step("portfolio_token_forecast", _forecast))

    # 4. Control loop — recompute the routing policy overlay.
    def _controller() -> dict[str, Any]:
        controller = importlib.import_module("control_plane.controller")
        decision = controller.run_once()
        return {
            "c_to_t_threshold": getattr(decision, "c_to_t_threshold", None),
            "previous_threshold": getattr(decision, "previous_threshold", None),
            "direction": getattr(decision, "direction", None),
            "allow_paid_spill": getattr(decision, "allow_paid_spill", None),
            "staleness_fallback": getattr(decision, "staleness_fallback", None),
        }

    steps.append(_refresh_step("controller", _controller))

    # 5. Dashboard & metrics — emit the chromatic_* series.
    def _exporter() -> dict[str, Any]:
        exporter = importlib.import_module("dashboards.exporter.token_economy_exporter")
        rendered = exporter.export(fmt="json")
        return {"bytes": len(rendered)}

    steps.append(_refresh_step("token_economy_exporter", _exporter))

    return steps


def _build_suggestions(checks: list[CheckResult]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []

    for c in checks:
        if c.status == "pass":
            continue

        if c.name == "audit_mcp_context":
            suggestions.append(
                {
                    "id": "token-gov-mcp-trim",
                    "title": "Trim MCP token surface below profile warning threshold",
                    "goal": "Disable or prune heavy MCP descriptors and re-run audit_mcp_context + session_context_report",
                    "priority": "P1",
                    "tier": 1,
                    "type": "task",
                    "context": {
                        "category": "token_governance",
                        "source_check": c.name,
                        "message": c.message,
                    },
                }
            )

        if c.name == "validate_workflow_token_governance":
            suggestions.append(
                {
                    "id": "token-gov-workflow-guardrails",
                    "title": "Fix workflow token governance violations",
                    "goal": "Bring .claude/workflows and governance docs back into compliance with validate_workflow_token_governance.py",
                    "priority": "P1",
                    "tier": 1,
                    "type": "task",
                    "context": {
                        "category": "token_governance",
                        "source_check": c.name,
                        "message": c.message,
                    },
                }
            )

        if c.name == "daily_harness_audit_strict":
            suggestions.append(
                {
                    "id": "token-gov-daily-audit-remediation",
                    "title": "Remediate strict daily audit findings affecting token governance",
                    "goal": "Resolve red/yellow strict daily audit findings and enforce green baseline",
                    "priority": "P1" if c.status == "fail" else "P2",
                    "tier": 2,
                    "type": "task",
                    "context": {
                        "category": "token_governance",
                        "source_check": c.name,
                        "message": c.message,
                    },
                }
            )

        if c.name == "session_context_report":
            suggestions.append(
                {
                    "id": "token-gov-context-budget",
                    "title": "Reduce session context budget pressure and warnings",
                    "goal": "Address session_context_report warnings and keep pre-session context within budget",
                    "priority": "P2",
                    "tier": 2,
                    "type": "task",
                    "context": {
                        "category": "token_governance",
                        "source_check": c.name,
                        "message": c.message,
                    },
                }
            )

    # Deduplicate by id while preserving order.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for s in suggestions:
        sid = s["id"]
        if sid in seen:
            continue
        seen.add(sid)
        unique.append(s)
    return unique


def _enqueue_suggestions(suggestions: list[dict[str, Any]], dry_run: bool) -> list[dict[str, Any]]:
    existing = {e.id: e for e in list_entries(repo_root=REPO)}
    queued: list[dict[str, Any]] = []

    for s in suggestions:
        sid = s["id"]
        if sid in existing:
            queued.append(
                {
                    "id": sid,
                    "status": "skipped_existing",
                    "reason": existing[sid].status,
                }
            )
            continue

        payload = {
            "id": sid,
            "source": "workflow",
            "kind": "goal",
            "status": "queued",
            "title": s["title"],
            "goal": s["goal"],
            "priority": s["priority"],
            "type": s["type"],
            "tier": s["tier"],
            "lane": "review",
            "context": s.get("context", {}),
        }

        if dry_run:
            queued.append({"id": sid, "status": "dry_run", "payload": payload})
            continue

        entry = append_entry(payload, repo_root=REPO)
        queued.append({"id": sid, "status": "queued", "queued_at": entry.queued_at})

    return queued


def _write_reports(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    out_dir = REPO / "07_LOGS_AND_AUDIT" / "token_governance"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_path = out_dir / f"token_governance_{ts}.json"
    latest_path = out_dir / "latest.json"
    log_path = out_dir / "history.jsonl"

    run_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    summary_md = out_dir / "latest.md"
    counts = report["counts"]
    lines = [
        "# Token Governance Closed Loop",
        "",
        f"- Timestamp: {report['timestamp']}",
        f"- Status: {report['status'].upper()}",
        f"- Pass: {counts['pass']}",
        f"- Warn: {counts['warn']}",
        f"- Fail: {counts['fail']}",
        "",
        "## Checks",
        "",
    ]
    for c in report["checks"]:
        lines.append(f"- {c['status'].upper()} {c['name']}: {c['message']}")
    lines += ["", "## Refresh Chain", ""]
    if report.get("refresh_steps"):
        for r in report["refresh_steps"]:
            extra = r.get("error", "")
            lines.append(f"- {r['status'].upper()} {r['name']}" + (f": {extra}" if extra else ""))
    else:
        lines.append("- Refresh chain skipped.")
    lines += ["", "## Suggestions", ""]
    if report["suggestions"]:
        for s in report["suggestions"]:
            lines.append(f"- {s['id']}: {s['title']}")
    else:
        lines.append("- No suggestions generated.")
    lines += ["", "## Queue Actions", ""]
    if report["queue_actions"]:
        for q in report["queue_actions"]:
            lines.append(f"- {q['id']}: {q['status']}")
    else:
        lines.append("- No queue actions.")

    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_path, latest_path, summary_md


def _drain_intake(limit: int, dry_run: bool) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "auto_intake.py"),
        "--limit",
        str(limit),
    ]
    if dry_run:
        cmd.append("--dry-run")
    code, out, err = _run(cmd, timeout=240)
    data = _parse_json(out) or {}
    return {
        "ok": code == 0,
        "returncode": code,
        "stderr": err[-1000:],
        "result": data,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Token governance closed loop audit + suggestions")
    parser.add_argument("--profile", default="harness_dev", help="MCP profile for audit_mcp_context")
    parser.add_argument(
        "--enqueue-suggestions",
        action="store_true",
        help="Append generated suggestions to intake queue",
    )
    parser.add_argument(
        "--drain-intake",
        action="store_true",
        help="Run auto_intake after enqueueing suggestions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not mutate intake queue; only simulate",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip the control-plane refresh chain (proxy->telemetry->forecast->controller->exporter)",
    )
    parser.add_argument("extras", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    ignored = [x for x in args.extras if x.strip() in {".", "./", ".\\"}]
    if ignored:
        print(f"INFO ignored placeholder args: {' '.join(ignored)}")

    checks = [
        _check_session_context(),
        _check_mcp_audit(args.profile),
        _check_workflow_token_governance(),
        _check_daily_strict(),
    ]

    counts = {
        "pass": sum(1 for c in checks if c.status == "pass"),
        "warn": sum(1 for c in checks if c.status == "warn"),
        "fail": sum(1 for c in checks if c.status == "fail"),
    }
    status = "green"
    if counts["fail"]:
        status = "red"
    elif counts["warn"]:
        status = "yellow"

    refresh_steps: list[dict[str, Any]] = []
    if not args.skip_refresh:
        refresh_steps = _refresh_control_plane()

    suggestions = _build_suggestions(checks)
    queue_actions: list[dict[str, Any]] = []

    if args.enqueue_suggestions:
        queue_actions = _enqueue_suggestions(suggestions, dry_run=args.dry_run)

    intake_result: dict[str, Any] | None = None
    if args.drain_intake and args.enqueue_suggestions:
        # Use number of generated suggestions as a practical processing cap.
        intake_result = _drain_intake(limit=max(len(suggestions), 1), dry_run=args.dry_run)

    report = {
        "audit": "token_governance_closed_loop",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "root": str(REPO),
        "status": status,
        "counts": counts,
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "returncode": c.returncode,
                "message": c.message,
                "command": c.command,
            }
            for c in checks
        ],
        "refresh_steps": refresh_steps,
        "suggestions": suggestions,
        "queue_actions": queue_actions,
        "intake_result": intake_result,
    }

    run_path, latest_path, summary_md = _write_reports(report)

    print(
        json.dumps(
            {
                **report,
                "artifacts": {
                    "run_json": str(run_path.relative_to(REPO)).replace("\\", "/"),
                    "latest_json": str(latest_path.relative_to(REPO)).replace("\\", "/"),
                    "latest_md": str(summary_md.relative_to(REPO)).replace("\\", "/"),
                },
            },
            indent=2,
        )
    )

    return 1 if status == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
