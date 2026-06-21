"""Tests for self_heal.py — detection, band checks, and repair logic."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"


def _load(name: str, rel: str):
    path = _RUNTIME / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("workflows.models", "workflows/models.py")
_sh = _load("workflows.self_heal", "workflows/self_heal.py")

ConfidenceRecord = _models.ConfidenceRecord
WorkflowDecision = _models.WorkflowDecision

in_self_heal_band = _sh.in_self_heal_band
needs_self_heal = _sh.needs_self_heal
enqueue_graph_subtasks = _sh.enqueue_graph_subtasks
SELF_HEAL_MIN = _sh.SELF_HEAL_MIN
SELF_HEAL_MAX = _sh.SELF_HEAL_MAX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(score: float, decision: WorkflowDecision = WorkflowDecision.PLAN_ONLY) -> ConfidenceRecord:
    return ConfidenceRecord(
        confidence_score=score,
        risk_level="low",
        scope_clarity=0.8,
        evidence_quality=0.8,
        reversibility="reversible",
        tool_budget_fit=True,
        cmp_decision="plan",
        workflow_decision=decision,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSelfHeal:
    # ------------------------------------------------------------------
    # in_self_heal_band
    # ------------------------------------------------------------------

    def test_band_lower_boundary(self):
        assert in_self_heal_band(SELF_HEAL_MIN) is True

    def test_band_upper_boundary(self):
        assert in_self_heal_band(SELF_HEAL_MAX) is True

    def test_band_midpoint(self):
        mid = (SELF_HEAL_MIN + SELF_HEAL_MAX) / 2
        assert in_self_heal_band(mid) is True

    def test_below_band(self):
        assert in_self_heal_band(SELF_HEAL_MIN - 1) is False

    def test_above_band(self):
        assert in_self_heal_band(SELF_HEAL_MAX + 1) is False

    def test_zero_score_not_in_band(self):
        assert in_self_heal_band(0.0) is False

    def test_full_score_not_in_band(self):
        assert in_self_heal_band(100.0) is False

    # ------------------------------------------------------------------
    # needs_self_heal
    # ------------------------------------------------------------------

    def test_needs_self_heal_true_in_band_plan_only(self):
        rec = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(rec) is True

    def test_needs_self_heal_false_execute_decision(self):
        rec = _make_record(60.0, WorkflowDecision.EXECUTE)
        assert needs_self_heal(rec) is False

    def test_needs_self_heal_false_halt_decision(self):
        rec = _make_record(60.0, WorkflowDecision.HALT)
        assert needs_self_heal(rec) is False

    def test_needs_self_heal_false_score_above_band(self):
        rec = _make_record(90.0, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(rec) is False

    def test_needs_self_heal_false_score_below_band(self):
        rec = _make_record(30.0, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(rec) is False

    # ------------------------------------------------------------------
    # enqueue_graph_subtasks — with mocked intake.queue
    # ------------------------------------------------------------------

    def _sample_graph(self, wf_id: str = "WF-001") -> dict:
        return {
            "workflow_id": wf_id,
            "tasks": [
                {"task_id": "T1", "role": "scout", "title": "Scout phase"},
                {"task_id": "T2", "role": "worker", "title": "Build phase"},
                {"task_id": "T3", "role": "verifier", "title": "Verify phase"},
            ],
        }

    def test_enqueue_returns_ids_for_scout_and_worker(self, tmp_path):
        graph = self._sample_graph()
        captured = []

        fake_queue = MagicMock()
        fake_queue.append_entry = lambda entry: captured.append(entry)

        with patch.dict(sys.modules, {"intake.queue": fake_queue}):
            ids = enqueue_graph_subtasks(graph, bead_id="B1", parent_score=60.0)

        # Only scout + worker, not verifier
        assert len(ids) == 2
        assert all(id_.startswith("sh-WF-001-") for id_ in ids)

    def test_enqueue_skips_non_scout_worker(self, tmp_path):
        graph = {
            "workflow_id": "WF-X",
            "tasks": [
                {"task_id": "V1", "role": "verifier", "title": "Verify"},
                {"task_id": "P1", "role": "planner", "title": "Plan"},
            ],
        }
        fake_queue = MagicMock()
        fake_queue.append_entry = MagicMock()

        with patch.dict(sys.modules, {"intake.queue": fake_queue}):
            ids = enqueue_graph_subtasks(graph, bead_id="B2", parent_score=55.0)

        assert ids == []
        fake_queue.append_entry.assert_not_called()

    def test_enqueue_id_truncated_to_80_chars(self, tmp_path):
        long_wf = "WF-" + "x" * 100
        graph = {
            "workflow_id": long_wf,
            "tasks": [{"task_id": "T99", "role": "scout", "title": "Long"}],
        }
        fake_queue = MagicMock()
        captured = []
        fake_queue.append_entry = lambda entry: captured.append(entry)

        with patch.dict(sys.modules, {"intake.queue": fake_queue}):
            ids = enqueue_graph_subtasks(graph, bead_id="", parent_score=60.0)

        assert len(ids) == 1
        assert len(ids[0]) <= 80

    def test_enqueue_context_payload_correct(self, tmp_path):
        graph = self._sample_graph("WF-CTX")
        captured = []

        fake_queue = MagicMock()
        fake_queue.append_entry = lambda entry: captured.append(entry)

        with patch.dict(sys.modules, {"intake.queue": fake_queue}):
            enqueue_graph_subtasks(graph, bead_id="B99", parent_score=63.0)

        assert len(captured) == 2  # scout + worker
        ctx = captured[0]["context"]
        assert ctx["self_heal"] is True
        assert ctx["workflow_id"] == "WF-CTX"
        assert ctx["parent_confidence"] == 63.0
        assert captured[0]["bead_id"] == "B99"

    def test_enqueue_empty_tasks(self, tmp_path):
        graph = {"workflow_id": "WF-EMPTY", "tasks": []}
        fake_queue = MagicMock()
        fake_queue.append_entry = MagicMock()

        with patch.dict(sys.modules, {"intake.queue": fake_queue}):
            ids = enqueue_graph_subtasks(graph, bead_id="", parent_score=55.0)

        assert ids == []

    def test_enqueue_missing_workflow_id_uses_default(self, tmp_path):
        graph = {"tasks": [{"task_id": "T1", "role": "worker", "title": "Work"}]}
        captured = []
        fake_queue = MagicMock()
        fake_queue.append_entry = lambda entry: captured.append(entry)

        with patch.dict(sys.modules, {"intake.queue": fake_queue}):
            ids = enqueue_graph_subtasks(graph, bead_id="", parent_score=60.0)

        assert len(ids) == 1
        assert "WF-self-heal" in ids[0]

    # ------------------------------------------------------------------
    # apply_self_heal — full integration path with mocks
    # ------------------------------------------------------------------

    def test_apply_self_heal_returns_expected_keys(self, tmp_path):
        """apply_self_heal should return a dict with canonical keys."""
        rec = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        bead = {"bead_id": "B10", "title": "Rebuild subsystem"}

        fake_graph = {
            "workflow_id": "WF-HEAL",
            "tasks": [
                {"task_id": "S1", "role": "scout", "title": "Scout"},
                {"task_id": "W1", "role": "worker", "title": "Work"},
            ],
        }
        fake_graph_path = tmp_path / "active-graph.json"
        fake_graph_path.write_text(json.dumps(fake_graph))

        fake_queue = MagicMock()
        fake_queue.append_entry = MagicMock()

        with (
            patch.dict(sys.modules, {"intake.queue": fake_queue}),
            patch("workflows.roles.build_standard_pipeline", return_value=fake_graph),
            patch("workflows.roles.write_active_graph", return_value=fake_graph_path),
        ):
            # Ensure roles module stub is available
            fake_roles = MagicMock()
            fake_roles.build_standard_pipeline = MagicMock(return_value=fake_graph)
            fake_roles.write_active_graph = MagicMock(return_value=fake_graph_path)
            sys.modules.setdefault("workflows.roles", fake_roles)

            _sh2 = _load("workflows.self_heal", "workflows/self_heal.py")

            result = _sh2.apply_self_heal(tmp_path, bead, rec)

        assert result["self_heal"] is True
        assert "band" in result
        assert "task_graph_path" in result
        assert "tasks" in result
        assert "intake_enqueued" in result
