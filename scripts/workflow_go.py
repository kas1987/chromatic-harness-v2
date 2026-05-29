#!/usr/bin/env python3
"""Bounded GO-mode CLI for the dynamic workflow runtime.

Usage:
  python scripts/workflow_go.py GO
  python scripts/workflow_go.py "GO AUDIT"
  python scripts/workflow_go.py "GO VERIFY"
  python scripts/workflow_go.py "GO BUILD"
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from workflows.confidence import mutation_allowed, score_task  # noqa: E402
from workflows.go_modes import mode_allows_mutation, mode_requires_swarm_approval, parse_go_mode  # noqa: E402
from workflows.models import GoMode, WorkflowDecision  # noqa: E402
from workflows.permission import Action, check_permission  # noqa: E402
from workflows.run_log import append_run_log, read_last_entry  # noqa: E402
from workflows.task_graph import load_task_graph  # noqa: E402
from workflows.verifier import verify_task_completion  # noqa: E402

ACTIVE_GRAPH = REPO / ".agents" / "workflows" / "active-graph.json"
HANDOFF = REPO / ".agents" / "handoffs" / "latest.json"


def _run_bd(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["bd", *args],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return ""
    return (proc.stdout or "") + (proc.stderr or "")


def _pick_ready_bead_id(output: str) -> str | None:
    for line in output.splitlines():
        m = re.search(r"(chromatic-harness-v2-[a-z0-9]+)", line)
        if m:
            return m.group(1)
    return None


def _load_handoff() -> dict:
    if not HANDOFF.is_file():
        return {}
    try:
        return json.loads(HANDOFF.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _bead_summary(bead_id: str) -> dict[str, str]:
    text = _run_bd(["show", bead_id])
    title = bead_id
    for line in text.splitlines():
        if line.strip() and not line.startswith("○") and not line.startswith("●"):
            title = line.strip()[:120]
            break
    return {"bead_id": bead_id, "title": title, "raw": text[:2000]}


def _score_for_bead(bead: dict[str, str], risk: str = "low") -> object:
    has_handoff = bool(_load_handoff())
    clarity = 75.0 if bead.get("title") else 50.0
    evidence = 80.0 if has_handoff else 60.0
    return score_task(
        objective_clarity=clarity,
        scope_clarity=clarity,
        evidence_quality=evidence,
        risk_level=risk,
    )


def _mission_packet_for_execute(bead: dict[str, str], record: object) -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "orchestrator_mod", _RUNTIME / "orchestrator" / "orchestrator.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    orch = mod.Orchestrator()
    mission = orch.create_mission_from_task(
        {
            "task_id": bead.get("bead_id", ""),
            "title": bead.get("title", ""),
            "role": "worker",
            "confidence_required": record.confidence_score,
            "bead_id": bead.get("bead_id", ""),
        }
    )
    return {
        "mission_id": mission.mission_id,
        "objective": mission.objective,
        "agent_role": mission.agent_role,
        "confidence_required": mission.confidence_required,
        "metadata": mission.metadata,
    }


def cmd_go_audit() -> int:
    ready = _run_bd(["ready"])
    bead_id = _pick_ready_bead_id(ready)
    handoff = _load_handoff()
    graph_status = "none"
    if ACTIVE_GRAPH.is_file():
        graph_status = "present"
    payload = {
        "mode": "GO AUDIT",
        "bead_id": bead_id,
        "handoff": handoff,
        "active_graph": graph_status,
        "bd_ready_excerpt": ready[:1500],
    }
    append_run_log(REPO, payload)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_go_verify() -> int:
    last = read_last_entry(REPO)
    if not last:
        print(json.dumps({"error": "no prior workflow run in log"}, indent=2))
        return 1
    bead_id = last.get("bead_id") or last.get("task_id", "unknown")
    record = score_task(objective_clarity=70, scope_clarity=70, evidence_quality=70)
    risk = record.risk_level
    verifier_approved = record.workflow_decision == WorkflowDecision.EXECUTE

    from workflows.git_policy import evaluate_git_pipeline  # noqa: E402

    pipeline = evaluate_git_pipeline(
        confidence=record.confidence_score,
        risk_level=risk,
        verifier_approved=verifier_approved,
        tests_passed=False,
        ci_passed=False,
        has_staged_changes=True,
    )
    result = {
        "mode": "GO VERIFY",
        "last_run": last,
        "confidence": record.to_dict(),
        "verifier_approved": verifier_approved,
        "verifier": {"decision": "approve" if verifier_approved else "request_changes"},
        "git_pipeline": pipeline.to_dict(),
        "verdict": "ok" if record.workflow_decision != WorkflowDecision.HALT else "needs_review",
        "next": f"python scripts/workflow_git.py ship --from-log --verifier approve --run-tests"
        if pipeline.commit
        else f"bd show {bead_id}",
    }
    append_run_log(REPO, result)
    print(json.dumps(result, indent=2))
    return 0


def cmd_go_build(bead_id: str | None, record: object) -> int:
    if not bead_id:
        print(json.dumps({"error": "no ready bead for GO BUILD"}, indent=2))
        return 1
    perm = check_permission(Action.EDIT_ASSIGNED, confidence=record.confidence_score)
    if not perm.allowed:
        print(json.dumps({"error": perm.reason, "decision": "halt"}, indent=2))
        return 1
    mission_hint = {
        "bead_id": bead_id,
        "decision": record.workflow_decision.value,
        "message": "Run /close-issue or implement with scoped files only",
    }
    append_run_log(REPO, {"mode": "GO BUILD", **mission_hint, "confidence": record.to_dict()})
    print(json.dumps(mission_hint, indent=2))
    return 0


def cmd_go(mode: GoMode) -> int:
    if mode_requires_swarm_approval(mode):
        msg = {
            "error": "GO SWARM requires approved task graph and human approval",
            "decision": "halt",
        }
        print(json.dumps(msg, indent=2))
        append_run_log(REPO, {"mode": mode.value, **msg})
        return 1

    if mode == GoMode.GO_AUDIT:
        return cmd_go_audit()
    if mode == GoMode.GO_VERIFY:
        return cmd_go_verify()

    if mode == GoMode.GO_SHIP:
        import subprocess as sp

        proc = sp.run(
            [sys.executable, str(REPO / "scripts" / "workflow_git.py"), "ship", "--from-log", "--run-tests"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=600,
        )
        print(proc.stdout or proc.stderr)
        return proc.returncode

    ready = _run_bd(["ready"])
    bead_id = _pick_ready_bead_id(ready)
    bead = _bead_summary(bead_id) if bead_id else {"bead_id": "", "title": ""}

    risk = "low"
    if ACTIVE_GRAPH.is_file():
        try:
            graph = load_task_graph(ACTIVE_GRAPH)
            risk = graph.risk_level
        except (ValueError, json.JSONDecodeError):
            pass

    record = _score_for_bead(bead, risk=risk)

    if mode == GoMode.GO_DEEP:
        from workflows.roles import build_standard_pipeline, write_active_graph

        objective = bead.get("title") or "Next harness task"
        graph = build_standard_pipeline(objective, bead_id=bead_id or "")
        graph_path = write_active_graph(graph, repo_root=REPO)
        out = {
            "mode": "GO DEEP",
            "bead_id": bead_id,
            "decision": "plan_only",
            "confidence": record.to_dict(),
            "task_graph_path": str(graph_path.relative_to(REPO)),
            "tasks": [t["task_id"] for t in graph["tasks"]],
            "next": "python scripts/auto_intake.py && workflow_go GO",
        }
        append_run_log(REPO, out)
        print(json.dumps(out, indent=2))
        return 0

    if mode == GoMode.GO_BUILD:
        if not mutation_allowed(record):
            print(json.dumps({"decision": "plan_only", "confidence": record.to_dict()}, indent=2))
            return 0
        return cmd_go_build(bead_id, record)

    if not mode_allows_mutation(mode):
        return cmd_go_audit()

    if record.workflow_decision == WorkflowDecision.HALT:
        out = {"mode": mode.value, "bead_id": bead_id, "decision": "halt", "confidence": record.to_dict()}
        append_run_log(REPO, out)
        print(json.dumps(out, indent=2))
        return 1

    if record.workflow_decision == WorkflowDecision.PLAN_ONLY:
        from workflows.self_heal import apply_self_heal, needs_self_heal

        if needs_self_heal(record):
            heal = apply_self_heal(REPO, bead, record)
            out = {
                "mode": mode.value,
                "bead_id": bead_id,
                "decision": "self_heal",
                "confidence": record.to_dict(),
                **heal,
                "next": "python scripts/auto_intake.py && python scripts/workflow_go.py GO",
            }
            append_run_log(REPO, out)
            print(json.dumps(out, indent=2))
            return 0

        out = {
            "mode": mode.value,
            "bead_id": bead_id,
            "decision": "plan_only",
            "confidence": record.to_dict(),
            "next": "GO DEEP or improve handoff / scope",
        }
        append_run_log(REPO, out)
        print(json.dumps(out, indent=2))
        return 0

    perm = check_permission(Action.EDIT_ASSIGNED, confidence=record.confidence_score)
    if not perm.allowed:
        out = {"decision": "halt", "reason": perm.reason, "confidence": record.to_dict()}
        append_run_log(REPO, out)
        print(json.dumps(out, indent=2))
        return 1

    out = {
        "mode": mode.value,
        "bead_id": bead_id,
        "bead_title": bead.get("title"),
        "decision": "execute",
        "confidence": record.to_dict(),
        "mission": _mission_packet_for_execute(bead, record),
        "next": f"/close-issue {bead_id}" if bead_id else "bd ready",
    }
    append_run_log(REPO, out)
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    raw = " ".join(argv)
    try:
        mode = parse_go_mode(raw)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    return cmd_go(mode)


if __name__ == "__main__":
    raise SystemExit(main())
