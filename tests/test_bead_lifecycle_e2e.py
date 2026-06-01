"""End-to-end bead lifecycle coverage: intake -> score -> route -> validate -> promote."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from intake.auto_intake import drain_queue
from intake.queue import append_entry
from router.adapters.base import AdapterHealth, BaseAdapter
from router.confidence import ConfidenceGate
from router.contracts import (
    OutputType,
    PrivacyClass,
    RouteAudit,
    RouteConfidence,
    RouteConstraints,
    RouteInput,
    RouteOutput,
    RouteRequest,
    RouteResponse,
    TaskType,
)
from router.router import ChromaticRouter
from workflows.confidence import mutation_allowed, score_task
from workflows.models import TaskNode, WorkflowDecision
from workflows.verifier import verify_task_completion

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_bead_lifecycle_intake_route_validate_promote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.queue as queue_mod
    from scripts import promote_to_wiki as p2w

    queue_path = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(queue_mod, "default_queue_path", lambda repo_root=None: queue_path)

    append_entry(
        {
            "id": "e2e-goal-1",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Implement lifecycle path",
            "goal": "Implement lifecycle path",
            "priority": "P1",
            "type": "task",
        },
        path=queue_path,
    )

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if "create" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                "Created issue: chromatic-harness-v2-lc1\n",
                "",
            )
        if "update" in cmd and "--claim" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "Updated issue\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "unexpected command")

    report = drain_queue(
        repo_root=tmp_path,
        queue_path=queue_path,
        limit=1,
        runner=fake_runner,
        dry_run=False,
        claim=True,
    )
    assert report.processed == 1
    assert report.results[0].bead_id == "chromatic-harness-v2-lc1"

    confidence = score_task(
        objective_clarity=90,
        scope_clarity=85,
        evidence_quality=85,
        reversibility=90,
        tool_fit=85,
        risk_awareness=80,
        testability=85,
    )
    assert confidence.workflow_decision == WorkflowDecision.EXECUTE

    req = RouteRequest(
        request_id="route-e2e-1",
        task_id=report.results[0].bead_id,
        task_type=TaskType.CODING,
        objective="Implement lifecycle path",
        input=RouteInput(messages=[{"role": "user", "content": "Do the task"}]),
        constraints=RouteConstraints(
            privacy_class=PrivacyClass.P1,
            max_cost_usd=1.0,
            allow_openhuman=True,
        ),
        confidence=RouteConfidence(
            score=confidence.confidence_score,
            band=ConfidenceGate.band_from_score(confidence.confidence_score),
        ),
        preferred_provider="openhuman",
        fallback_chain=["mock"],
        audit=RouteAudit(caller="pytest-e2e", repo="chromatic-harness-v2"),
    )
    routed = await ChromaticRouter().route(req)
    assert routed.selected_provider == "mock"
    assert routed.fallback_used is True

    task = TaskNode.from_dict(
        {
            "task_id": report.results[0].bead_id,
            "title": "Implement lifecycle path",
            "assigned_model": "kimi",
            "role": "worker",
            "tool_budget": 10,
            "confidence_required": 75,
            "risk_level": "low",
            "status": "pending",
            "allowed_files": ["scripts/"],
            "acceptance_criteria": ["tests pass"],
        }
    )
    verdict = verify_task_completion(
        task,
        files_touched=["scripts/auto_intake.py"],
        confidence_score=confidence.confidence_score,
        risk_level="low",
        tools_used=2,
        validation="pytest ok",
    )
    assert verdict.decision == "approve"

    learnings = tmp_path / ".agents" / "learnings"
    learnings.mkdir(parents=True, exist_ok=True)
    src = learnings / "lifecycle.md"
    src.write_text(
        "---\nname: Lifecycle Learning\nconfidence: high\n---\n\nValidated lifecycle path.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(p2w, "REPO", tmp_path)
    monkeypatch.setattr(p2w, "LEARNINGS", learnings)
    monkeypatch.setattr(
        p2w,
        "AUTO_TURN_REPORTS",
        tmp_path / "07_LOGS_AND_AUDIT" / "auto_turn_thresholds",
    )

    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    candidates = p2w._discover_candidates(0.75)
    assert len(candidates) == 1

    rel = p2w._promote_one(src, wiki, execute=True)
    assert rel is not None
    assert (wiki / rel).is_file()


def test_bead_lifecycle_confidence_plan_only_and_halt_block_execution_handoff():
    plan_only = score_task(
        objective_clarity=62,
        scope_clarity=62,
        evidence_quality=62,
        reversibility=70,
        tool_fit=70,
        risk_awareness=62,
        testability=62,
    )
    assert plan_only.workflow_decision == WorkflowDecision.PLAN_ONLY
    assert mutation_allowed(plan_only) is False

    halt = score_task(
        objective_clarity=40,
        scope_clarity=40,
        evidence_quality=40,
        reversibility=40,
        tool_fit=40,
        risk_awareness=40,
        testability=40,
    )
    assert halt.workflow_decision == WorkflowDecision.HALT
    assert mutation_allowed(halt) is False


@pytest.mark.asyncio
async def test_bead_lifecycle_route_fallback_order_prefers_first_healthy_fallback():
    class FailingAdapter(BaseAdapter):
        async def health(self) -> AdapterHealth:
            return AdapterHealth(reachable=True, latency_ms=1)

        async def complete(self, req: RouteRequest) -> RouteResponse:
            raise RuntimeError("forced adapter failure")

    class PassingAdapter(BaseAdapter):
        async def health(self) -> AdapterHealth:
            return AdapterHealth(reachable=True, latency_ms=1)

        async def complete(self, req: RouteRequest) -> RouteResponse:
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                selected_model="stub-ok",
                route_reason="stub_success",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                output=RouteOutput(type=OutputType.TEXT, content="ok"),
            )

    router = ChromaticRouter(
        adapters={
            "openrouter": FailingAdapter("openrouter", {"enabled": True}),
            "openai": PassingAdapter("openai", {"enabled": True}),
        }
    )
    req = RouteRequest(
        request_id="route-fallback-order-1",
        task_id="chromatic-harness-v2-lc3",
        task_type=TaskType.CODING,
        objective="Verify fallback order",
        input=RouteInput(messages=[{"role": "user", "content": "fallback order"}]),
        constraints=RouteConstraints(privacy_class=PrivacyClass.P1, max_cost_usd=10.0),
        confidence=RouteConfidence(score=90, band=ConfidenceGate.band_from_score(90)),
        preferred_provider="openrouter",
        fallback_chain=["openai", "mock"],
        audit=RouteAudit(caller="pytest-e2e", repo="chromatic-harness-v2"),
    )
    routed = await router.route(req)
    assert routed.selected_provider == "openai"
    assert routed.fallback_used is True


@pytest.mark.asyncio
async def test_bead_lifecycle_openrouter_first_with_local_lmstudio_fallback():
    class FailingAdapter(BaseAdapter):
        async def health(self) -> AdapterHealth:
            return AdapterHealth(reachable=True, latency_ms=1)

        async def complete(self, req: RouteRequest) -> RouteResponse:
            raise RuntimeError("forced adapter failure")

    class PassingAdapter(BaseAdapter):
        async def health(self) -> AdapterHealth:
            return AdapterHealth(reachable=True, latency_ms=1)

        async def complete(self, req: RouteRequest) -> RouteResponse:
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                selected_model="local-stub",
                route_reason="local_fallback_success",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                output=RouteOutput(type=OutputType.TEXT, content="local-ok"),
            )

    router = ChromaticRouter(
        adapters={
            "openrouter": FailingAdapter("openrouter", {"enabled": True}),
            "lmstudio": PassingAdapter("lmstudio", {"enabled": True}),
        }
    )
    req = RouteRequest(
        request_id="route-local-fallback-1",
        task_id="chromatic-harness-v2-lc4",
        task_type=TaskType.CODING,
        objective="Prefer openrouter, fallback to local",
        input=RouteInput(messages=[{"role": "user", "content": "local fallback"}]),
        constraints=RouteConstraints(privacy_class=PrivacyClass.P1, max_cost_usd=10.0),
        confidence=RouteConfidence(score=90, band=ConfidenceGate.band_from_score(90)),
        preferred_provider="openrouter",
        fallback_chain=["lmstudio", "mock"],
        audit=RouteAudit(caller="pytest-e2e", repo="chromatic-harness-v2"),
    )
    routed = await router.route(req)
    assert routed.selected_provider == "lmstudio"
    assert routed.fallback_used is True


def test_bead_lifecycle_verifier_rejects_out_of_scope_files():
    confidence = score_task(
        objective_clarity=88,
        scope_clarity=82,
        evidence_quality=80,
        reversibility=90,
        tool_fit=80,
        risk_awareness=80,
        testability=78,
    )
    assert confidence.workflow_decision == WorkflowDecision.EXECUTE

    task = TaskNode.from_dict(
        {
            "task_id": "chromatic-harness-v2-lc2",
            "title": "Scope-limited work",
            "assigned_model": "kimi",
            "role": "worker",
            "tool_budget": 10,
            "confidence_required": 75,
            "risk_level": "low",
            "status": "pending",
            "allowed_files": ["scripts/"],
            "acceptance_criteria": ["tests pass"],
        }
    )
    verdict = verify_task_completion(
        task,
        files_touched=["docs/out_of_scope.md"],
        confidence_score=confidence.confidence_score,
        risk_level="low",
        tools_used=2,
        validation="pytest ok",
    )
    assert verdict.decision in ("reject", "request_changes")
    assert verdict.issues


def test_bead_lifecycle_subprocess_poll_and_auto_intake_roundtrip(tmp_path: Path):
    db_path = tmp_path / "chromatic_inbox.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE queue_items (
                id TEXT PRIMARY KEY,
                subject TEXT,
                source TEXT,
                status TEXT,
                priority TEXT,
                created_at TEXT,
                body TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO queue_items (id, subject, source, status, priority, created_at, body)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pytest-e2e-1",
                "Inbox E2E Intake",
                "pytest",
                "pending",
                "P1",
                "2026-05-30T00:00:00Z",
                "Create one goal from inbox item",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    queue_path = REPO / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"
    sync_state_path = REPO / ".agents" / "intake" / "inbox_sync.state.json"
    queue_before = queue_path.read_text(encoding="utf-8") if queue_path.is_file() else None
    sync_before = sync_state_path.read_text(encoding="utf-8") if sync_state_path.is_file() else None

    try:
        poll_proc = subprocess.run(
            [
                "python",
                str(REPO / "scripts" / "poll_inbox.py"),
                "--db",
                str(db_path),
                "--limit",
                "5",
                "--session-id",
                "pytest-e2e",
                "--lock-timeout",
                "5",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert poll_proc.returncode == 0, poll_proc.stderr or poll_proc.stdout
        poll_data = json.loads(poll_proc.stdout)
        assert poll_data.get("appended", 0) >= 1

        intake_proc = subprocess.run(
            [
                "python",
                str(REPO / "scripts" / "auto_intake.py"),
                "--dry-run",
                "--limit",
                "1",
                "--session-id",
                "pytest-e2e",
                "--lock-timeout",
                "5",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert intake_proc.returncode == 0, intake_proc.stderr or intake_proc.stdout
        intake_data = json.loads(intake_proc.stdout)
        assert intake_data.get("processed", 0) >= 1
    finally:
        if queue_before is None:
            if queue_path.exists():
                queue_path.unlink()
        else:
            queue_path.write_text(queue_before, encoding="utf-8")

        if sync_before is None:
            if sync_state_path.exists():
                sync_state_path.unlink()
        else:
            sync_state_path.parent.mkdir(parents=True, exist_ok=True)
            sync_state_path.write_text(sync_before, encoding="utf-8")
