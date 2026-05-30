#!/usr/bin/env python3
"""Assess Claude delegation pickup, reroute, and telemetry health.

This script gives a single answer to:
- Was delegation gated and emitted correctly?
- Do we have evidence Claude picked up work?
- Did observed provider/model behavior reroute from recommendation?
- Is telemetry coverage sufficient to prove the above?
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HANDOFF_DIR = REPO / ".agents" / "handoffs"
AUDIT_DIR = REPO / ".agents" / "audits" / "delegation"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path, max_lines: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for raw in lines[-max_lines:]:
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _stringify(row: dict[str, Any]) -> str:
    try:
        return json.dumps(row, sort_keys=True)
    except Exception:
        return str(row)


def _match_event(row: dict[str, Any], bead_id: str, task_text: str, run_id: str, task_id: str) -> bool:
    if run_id:
        if str(_pick(row, "run_id", "workflow_id") or "").strip() == run_id:
            return True
    if task_id:
        if str(_pick(row, "task_id", "bead_id", "request_id") or "").strip() == task_id:
            return True
    if not bead_id and not task_text:
        return False
    text = _stringify(row).lower()
    if bead_id and bead_id.lower() in text:
        return True
    if task_text and task_text.lower() in text:
        return True
    return False


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _display_path(path_value: str) -> str:
    p = Path(path_value)
    if not p.exists():
        return path_value
    try:
        return str(p.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    packet = _read_json(Path(args.packet), {})
    autoloop = _read_json(Path(args.autoloop), {})
    gov = _read_json(Path(args.governance), {})

    bead_id = str(args.bead_id or packet.get("bead_id") or "").strip()
    run_id = str(args.run_id or packet.get("run_id") or "").strip()
    task_id = str(args.task_id or packet.get("task_id") or packet.get("bead_id") or "").strip()
    task = str(args.task_contains or packet.get("task") or "").strip()
    task_probe = task[:80]

    provider_choices = packet.get("provider_choices") if isinstance(packet, dict) else []
    if not isinstance(provider_choices, list):
        provider_choices = []

    recommended_providers = [
        str(choice.get("provider") or "")
        for choice in provider_choices
        if isinstance(choice, dict) and choice.get("provider")
    ]
    recommended_models = [
        str(choice.get("model") or "")
        for choice in provider_choices
        if isinstance(choice, dict) and choice.get("model")
    ]

    workflow_rows = _read_jsonl(Path(args.workflow_log), max_lines=args.max_log_lines)
    agent_rows = _read_jsonl(Path(args.agent_log), max_lines=args.max_log_lines)

    matched_workflow = [r for r in workflow_rows if _match_event(r, bead_id, task_probe, run_id, task_id)]
    matched_agent = [r for r in agent_rows if _match_event(r, bead_id, task_probe, run_id, task_id)]

    observed_providers: list[str] = []
    observed_models: list[str] = []
    observed_statuses: list[str] = []

    for row in [*matched_workflow, *matched_agent]:
        provider = _pick(row, "provider", "selected_provider")
        model = _pick(row, "model", "selected_model", "assigned_model")
        status = _pick(row, "execution_status", "status", "result", "decision", "validation")
        if provider:
            observed_providers.append(str(provider))
        if model:
            observed_models.append(str(model))
        if status:
            observed_statuses.append(str(status))

    autoloop_cycles = autoloop.get("cycles") if isinstance(autoloop, dict) else []
    if not isinstance(autoloop_cycles, list):
        autoloop_cycles = []

    delegate_events = [
        c.get("claude_delegate")
        for c in autoloop_cycles
        if isinstance(c, dict) and isinstance(c.get("claude_delegate"), dict)
    ]
    delegate_ok = any(int(ev.get("returncode", 1)) == 0 for ev in delegate_events)

    decision = str(packet.get("decision") or "")
    pre_swarm_ok = bool((packet.get("pre_swarm_gate") or {}).get("ok")) if isinstance(packet, dict) else False
    spawn_obj = packet.get("spawn") if isinstance(packet, dict) else None
    spawn_ok = bool(spawn_obj.get("ok")) if isinstance(spawn_obj, dict) else None

    telemetry_cov = gov.get("canonical_coverage") if isinstance(gov, dict) else {}
    if not isinstance(telemetry_cov, dict):
        telemetry_cov = {}

    core_cov = {}
    for key in ("task_id", "provider", "model", "execution_status"):
        stats = telemetry_cov.get(key, {})
        coverage = stats.get("coverage") if isinstance(stats, dict) else None
        core_cov[key] = coverage

    reroute_detected = False
    reroute_reason = "unobserved"
    if observed_providers:
        reroute_detected = any(p not in recommended_providers for p in observed_providers if recommended_providers)
        if not recommended_providers:
            reroute_reason = "no recommendations captured"
        elif reroute_detected:
            reroute_reason = "observed provider outside recommended list"
        elif observed_providers and recommended_providers and observed_providers[0] != recommended_providers[0]:
            reroute_reason = "observed provider differs from top recommendation"
            reroute_detected = True
        else:
            reroute_reason = "observed providers align with recommendation"
    else:
        reroute_reason = "no per-task provider observations matched (telemetry correlation gap)"

    pickup_evidence = {
        "gate_execute": decision == "execute" and pre_swarm_ok,
        "delegate_invoked": delegate_ok or Path(args.prompt).is_file(),
        "spawn_ok": spawn_ok,
        "workflow_matches": len(matched_workflow),
        "agent_matches": len(matched_agent),
    }

    status = "red"
    if pickup_evidence["gate_execute"] and pickup_evidence["delegate_invoked"]:
        if pickup_evidence["workflow_matches"] > 0 or pickup_evidence["agent_matches"] > 0:
            status = "green"
        else:
            status = "yellow"

    recommendations: list[str] = []
    if status == "yellow":
        recommendations.append(
            "Add delegation run_id/task_id propagation into workflow and agent logs for reliable pickup correlation."
        )
    if core_cov.get("task_id") is not None and float(core_cov["task_id"] or 0.0) < 0.6:
        recommendations.append("Increase task_id coverage to >=0.60 in execution logs.")
    if core_cov.get("provider") is not None and float(core_cov["provider"] or 0.0) < 0.6:
        recommendations.append("Increase provider/model coverage to >=0.60 for reroute detection.")
    if not recommendations:
        recommendations.append("Delegation telemetry is healthy for current checks.")

    return {
        "audit": "claude_delegation_observability",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "inputs": {
            "packet": _display_path(args.packet),
            "prompt": _display_path(args.prompt),
            "autoloop": _display_path(args.autoloop),
            "governance": _display_path(args.governance),
        },
        "delegation": {
            "bead_id": bead_id or None,
            "run_id": run_id or None,
            "task_id": task_id or None,
            "task_probe": task_probe or None,
            "decision": decision or None,
            "pre_swarm_ok": pre_swarm_ok,
            "recommended_providers": recommended_providers,
            "recommended_models": recommended_models,
        },
        "pickup_evidence": pickup_evidence,
        "reroute": {
            "detected": reroute_detected,
            "reason": reroute_reason,
            "observed_providers": observed_providers[:10],
            "observed_models": observed_models[:10],
            "observed_statuses": observed_statuses[:10],
        },
        "telemetry_coverage": core_cov,
        "recommendations": recommendations,
    }


def write_report(report: dict[str, Any]) -> dict[str, str]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_json = AUDIT_DIR / f"delegation_observability_{ts}.json"
    latest_json = AUDIT_DIR / "latest.json"
    latest_md = AUDIT_DIR / "latest.md"

    run_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Claude Delegation Observability",
        "",
        f"Generated: {report.get('generated_at','')}",
        f"Status: {report.get('status','')}",
        "",
        "## Pickup Evidence",
        "",
        f"- gate_execute: {report.get('pickup_evidence',{}).get('gate_execute')}",
        f"- delegate_invoked: {report.get('pickup_evidence',{}).get('delegate_invoked')}",
        f"- workflow_matches: {report.get('pickup_evidence',{}).get('workflow_matches')}",
        f"- agent_matches: {report.get('pickup_evidence',{}).get('agent_matches')}",
        "",
        "## Reroute",
        "",
        f"- detected: {report.get('reroute',{}).get('detected')}",
        f"- reason: {report.get('reroute',{}).get('reason')}",
        "",
        "## Recommendations",
        "",
    ]
    for rec in report.get("recommendations", []):
        lines.append(f"- {rec}")

    latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "run_json": str(run_json.relative_to(REPO)).replace("\\", "/"),
        "latest_json": str(latest_json.relative_to(REPO)).replace("\\", "/"),
        "latest_md": str(latest_md.relative_to(REPO)).replace("\\", "/"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assess Claude delegation observability")
    parser.add_argument(
        "--packet",
        default=str(HANDOFF_DIR / "claude_delegate_packet.json"),
        help="Path to delegation packet JSON",
    )
    parser.add_argument(
        "--prompt",
        default=str(HANDOFF_DIR / "claude_delegate_prompt.md"),
        help="Path to delegation prompt markdown",
    )
    parser.add_argument(
        "--autoloop",
        default=str(REPO / ".agents" / "audits" / "bead_hygiene" / "latest_autoloop_report.json"),
        help="Path to latest autoloop report JSON",
    )
    parser.add_argument(
        "--governance",
        default=str(REPO / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json"),
        help="Path to governance intelligence latest JSON",
    )
    parser.add_argument(
        "--workflow-log",
        default=str(REPO / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"),
        help="Path to workflow run JSONL",
    )
    parser.add_argument(
        "--agent-log",
        default=str(REPO / "07_LOGS_AND_AUDIT" / "AGENT_RUN_LOG.jsonl"),
        help="Path to agent run JSONL",
    )
    parser.add_argument("--bead-id", default="", help="Optional bead id override")
    parser.add_argument("--run-id", default="", help="Optional run id override")
    parser.add_argument("--task-id", default="", help="Optional task id override")
    parser.add_argument("--task-contains", default="", help="Optional task text probe override")
    parser.add_argument("--max-log-lines", type=int, default=5000, help="Tail lines to inspect from each JSONL")
    parser.add_argument("--write", action="store_true", help="Write delegation observability artifacts")
    parser.add_argument("extras", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Harden accidental placeholder args on Windows operators.
    ignored = [x for x in args.extras if x.strip() in {".", "./", ".\\"}]
    if ignored:
        print(f"INFO ignored placeholder args: {' '.join(ignored)}")

    return args


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write:
        report["artifacts"] = write_report(report)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in {"green", "yellow"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
