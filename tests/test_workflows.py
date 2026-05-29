"""Tests for 02_RUNTIME/workflows dynamic workflow runtime."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "02_RUNTIME"
SCRIPT = REPO / "scripts" / "workflow_go.py"

from workflows.confidence import mutation_allowed, score_task  # noqa: E402
from workflows.models import TaskGraph, TaskNode, WorkflowDecision  # noqa: E402
from workflows.permission import Action, check_permission  # noqa: E402
from workflows.run_log import append_run_log, read_last_entry  # noqa: E402
from workflows.task_graph import load_task_graph, validate_graph_dict, validate_task_dict  # noqa: E402
from workflows.verifier import verify_task_completion  # noqa: E402
from workflows.git_policy import evaluate_git_pipeline  # noqa: E402
from workflows.self_heal import (  # noqa: E402
    apply_self_heal,
    in_self_heal_band,
    needs_self_heal,
)

GIT_SCRIPT = REPO / "scripts" / "workflow_git.py"


SAMPLE_GRAPH = {
    "workflow_id": "WF-TEST",
    "objective": "test objective",
    "risk_level": "low",
    "tasks": [
        {
            "task_id": "T-1",
            "title": "First task",
            "assigned_model": "kimi",
            "role": "worker",
            "tool_budget": 10,
            "confidence_required": 75,
            "risk_level": "low",
            "status": "pending",
            "allowed_files": ["src/foo.py"],
            "acceptance_criteria": ["tests pass"],
        }
    ],
}


def test_task_graph_validation_rejects_missing_keys():
    errors = validate_graph_dict({"workflow_id": "x"})
    assert any("missing keys" in e for e in errors)


def test_task_graph_load_roundtrip(tmp_path: Path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(SAMPLE_GRAPH), encoding="utf-8")
    graph = load_task_graph(path)
    assert graph.workflow_id == "WF-TEST"
    assert len(graph.tasks) == 1
    assert graph.tasks[0].role == "worker"


def test_permission_blocks_low_confidence_edit():
    result = check_permission(Action.EDIT_ASSIGNED, confidence=50)
    assert not result.allowed
    assert "75" in result.reason


def test_permission_blocks_unassigned_edit():
    result = check_permission(Action.EDIT_UNASSIGNED, confidence=90)
    assert not result.allowed


def test_permission_human_gate_for_delete():
    result = check_permission(Action.DELETE, confidence=95)
    assert result.requires_human


def test_confidence_halt_below_threshold():
    record = score_task(
        objective_clarity=20,
        scope_clarity=20,
        evidence_quality=20,
        reversibility=20,
        tool_fit=20,
        risk_awareness=20,
        testability=20,
    )
    assert record.workflow_decision == WorkflowDecision.HALT
    assert not mutation_allowed(record)


def test_self_heal_band_boundaries():
    assert in_self_heal_band(50)
    assert in_self_heal_band(69)
    assert not in_self_heal_band(49.9)
    assert not in_self_heal_band(70)


def test_needs_self_heal_on_mid_confidence_plan_only():
    record = score_task(
        objective_clarity=62,
        scope_clarity=62,
        evidence_quality=62,
        reversibility=70,
        tool_fit=70,
        risk_awareness=62,
        testability=62,
    )
    assert record.workflow_decision == WorkflowDecision.PLAN_ONLY
    assert needs_self_heal(record)


def test_apply_self_heal_writes_graph_and_intake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.queue as queue_mod

    queue_path = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(queue_mod, "default_queue_path", lambda _root=None: queue_path)

    record = score_task(objective_clarity=62, scope_clarity=62, evidence_quality=62)
    bead = {"bead_id": "chromatic-harness-v2-knd", "title": "Self-heal test bead"}
    result = apply_self_heal(tmp_path, bead, record)
    assert result["self_heal"] is True
    assert (tmp_path / ".agents" / "workflows" / "active-graph.json").is_file()
    assert len(result["intake_enqueued"]) >= 2
    lines = queue_path.read_text(encoding="utf-8").strip().splitlines()
    assert any("workflow" in line for line in lines)


def test_confidence_execute_at_high_scores():
    record = score_task(
        objective_clarity=95,
        scope_clarity=95,
        evidence_quality=95,
        reversibility=95,
        tool_fit=95,
        risk_awareness=95,
        testability=95,
    )
    assert record.workflow_decision == WorkflowDecision.EXECUTE
    assert mutation_allowed(record)


def test_verifier_rejects_out_of_scope_files():
    task = TaskNode.from_dict(SAMPLE_GRAPH["tasks"][0])
    result = verify_task_completion(
        task,
        files_touched=["other/bar.py"],
        confidence_score=80,
        risk_level="low",
        tools_used=2,
        validation="pytest ok",
    )
    assert result.decision in ("reject", "request_changes")
    assert result.issues


def test_verifier_approves_valid_run():
    task = TaskNode.from_dict(SAMPLE_GRAPH["tasks"][0])
    result = verify_task_completion(
        task,
        files_touched=["src/foo.py"],
        confidence_score=80,
        risk_level="low",
        tools_used=2,
        validation="pytest ok",
    )
    assert result.decision == "approve"


def test_run_log_append_and_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import workflows.run_log as run_log_mod

    monkeypatch.setattr(run_log_mod, "default_log_path", lambda root: tmp_path / "log.jsonl")
    append_run_log(REPO, {"task_id": "T-1", "result": "ok"})
    last = read_last_entry(REPO)
    assert last is not None
    assert last["task_id"] == "T-1"
    assert "timestamp" in last


def test_workflow_go_audit_subprocess():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "GO AUDIT"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip())
    assert data["mode"] == "GO AUDIT"


def test_workflow_go_swarm_blocked():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "GO SWARM"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 1
    assert "human approval" in proc.stdout.lower()


def test_orchestrator_create_mission_from_task():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "orchestrator_mod", RUNTIME / "orchestrator" / "orchestrator.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    orch = mod.Orchestrator()
    mission = orch.create_mission_from_task(
        {
            "task_id": "T-1",
            "title": "Implement gate",
            "role": "worker",
            "confidence_required": 80,
            "allowed_files": ["02_RUNTIME/workflows/"],
            "tool_budget": 15,
            "bead_id": "chromatic-harness-v2-test",
        }
    )
    assert mission.agent_role == "worker"
    assert mission.confidence_required == 80
    assert mission.metadata["bead_id"] == "chromatic-harness-v2-test"


def test_validate_task_dict_errors():
    errors = validate_task_dict({"task_id": "x"})
    assert errors


def test_git_pipeline_merge_requires_high_confidence():
    low = evaluate_git_pipeline(
        confidence=90,
        risk_level="low",
        verifier_approved=True,
        tests_passed=True,
        ci_passed=True,
    )
    assert low.commit and low.push and low.open_pr
    assert not low.merge

    high = evaluate_git_pipeline(
        confidence=96,
        risk_level="low",
        verifier_approved=True,
        tests_passed=True,
        ci_passed=True,
    )
    assert high.merge


def test_git_permission_commit_requires_verifier():
    assert not check_permission(Action.GIT_COMMIT, confidence=80, verifier_approved=False).allowed
    assert check_permission(Action.GIT_COMMIT, confidence=80, verifier_approved=True).allowed


def test_git_permission_push_requires_tests():
    assert not check_permission(
        Action.GIT_PUSH,
        confidence=90,
        verifier_approved=True,
        tests_passed=False,
    ).allowed
    assert check_permission(
        Action.GIT_PUSH,
        confidence=90,
        verifier_approved=True,
        tests_passed=True,
    ).allowed


def test_workflow_git_plan_subprocess():
    proc = subprocess.run(
        [
            sys.executable,
            str(GIT_SCRIPT),
            "plan",
            "--confidence",
            "92",
            "--verifier",
            "approve",
            "--tests-passed",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip())
    assert data["pipeline"]["commit"] is True
    assert data["dry_run"] is True
