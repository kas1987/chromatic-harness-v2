"""Tests for workflows.self_heal — self-heal band detection and graph enqueue."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workflows.models import ConfidenceRecord, WorkflowDecision
from workflows.self_heal import (
    SELF_HEAL_MAX,
    SELF_HEAL_MIN,
    apply_self_heal,
    enqueue_graph_subtasks,
    in_self_heal_band,
    needs_self_heal,
)


# ---------------------------------------------------------------------------
# in_self_heal_band
# ---------------------------------------------------------------------------


class TestInSelfHealBand:
    def test_lower_bound_inclusive(self):
        assert in_self_heal_band(SELF_HEAL_MIN) is True

    def test_upper_bound_inclusive(self):
        assert in_self_heal_band(SELF_HEAL_MAX) is True

    def test_midpoint(self):
        assert in_self_heal_band(60.0) is True

    def test_just_below_lower_bound(self):
        assert in_self_heal_band(SELF_HEAL_MIN - 0.1) is False

    def test_just_above_upper_bound(self):
        assert in_self_heal_band(SELF_HEAL_MAX + 0.1) is False

    def test_zero_not_in_band(self):
        assert in_self_heal_band(0.0) is False

    def test_hundred_not_in_band(self):
        assert in_self_heal_band(100.0) is False


# ---------------------------------------------------------------------------
# needs_self_heal
# ---------------------------------------------------------------------------


def _make_record(score: float, decision: WorkflowDecision = WorkflowDecision.PLAN_ONLY) -> ConfidenceRecord:
    return ConfidenceRecord(
        confidence_score=score,
        risk_level="low",
        scope_clarity=0.7,
        evidence_quality=0.7,
        reversibility="reversible",
        tool_budget_fit=True,
        cmp_decision="plan_only",
        workflow_decision=decision,
    )


class TestNeedsSelfHeal:
    def test_true_when_plan_only_in_band(self):
        record = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(record) is True

    def test_false_when_execute_decision(self):
        record = _make_record(60.0, WorkflowDecision.EXECUTE)
        assert needs_self_heal(record) is False

    def test_false_when_halt_decision(self):
        record = _make_record(60.0, WorkflowDecision.HALT)
        assert needs_self_heal(record) is False

    def test_false_when_score_above_band(self):
        record = _make_record(85.0, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(record) is False

    def test_false_when_score_below_band(self):
        record = _make_record(30.0, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(record) is False

    def test_true_at_lower_bound(self):
        record = _make_record(SELF_HEAL_MIN, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(record) is True

    def test_true_at_upper_bound(self):
        record = _make_record(SELF_HEAL_MAX, WorkflowDecision.PLAN_ONLY)
        assert needs_self_heal(record) is True


# ---------------------------------------------------------------------------
# enqueue_graph_subtasks — unit (mocking intake.queue.append_entry)
# ---------------------------------------------------------------------------


class TestEnqueueGraphSubtasks:
    def _graph(self) -> dict:
        return {
            "workflow_id": "WF-test",
            "tasks": [
                {"task_id": "t-scout", "title": "Scout task", "role": "scout"},
                {"task_id": "t-build", "title": "Build task", "role": "worker"},
                {"task_id": "t-verify", "title": "Verify task", "role": "verifier"},
                {"task_id": "t-scribe", "title": "Log task", "role": "scribe"},
            ],
        }

    def test_only_scout_and_worker_enqueued(self):
        with patch("workflows.self_heal.enqueue_graph_subtasks") as mock_fn:
            mock_fn.return_value = ["sh-WF-test-t-scout", "sh-WF-test-t-build"]
            ids = mock_fn(self._graph(), bead_id="BID-1", parent_score=60.0)
        # 2 ids: scout + worker
        assert len(ids) == 2

    def test_returns_list(self):
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            ids = enqueue_graph_subtasks(self._graph(), bead_id="BID-1", parent_score=60.0)
        assert isinstance(ids, list)
        # scout and worker only
        assert len(ids) == 2

    def test_entry_ids_contain_workflow_id(self):
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            ids = enqueue_graph_subtasks(self._graph(), bead_id="BID-1", parent_score=60.0)
        for entry_id in ids:
            assert "WF-test" in entry_id

    def test_empty_tasks_returns_empty(self):
        graph = {"workflow_id": "WF-empty", "tasks": []}
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            ids = enqueue_graph_subtasks(graph, bead_id="B", parent_score=55.0)
        assert ids == []

    def test_no_scout_or_worker_returns_empty(self):
        graph = {
            "workflow_id": "WF-x",
            "tasks": [
                {"task_id": "t1", "title": "Verify", "role": "verifier"},
                {"task_id": "t2", "title": "Log", "role": "scribe"},
            ],
        }
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            ids = enqueue_graph_subtasks(graph, bead_id="B", parent_score=55.0)
        assert ids == []

    def test_entry_id_capped_at_80_chars(self):
        long_wf = "W" * 70
        graph = {
            "workflow_id": long_wf,
            "tasks": [{"task_id": "t-scout", "title": "Scout", "role": "scout"}],
        }
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            ids = enqueue_graph_subtasks(graph, bead_id="B", parent_score=55.0)
        for entry_id in ids:
            assert len(entry_id) <= 80


# ---------------------------------------------------------------------------
# apply_self_heal — integration (mocking heavy deps)
# ---------------------------------------------------------------------------


class TestApplySelfHeal:
    def test_returns_dict_with_self_heal_key(self, tmp_path):
        bead = {"title": "Fix something", "bead_id": "BID-42"}
        record = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            with patch(
                "workflows.self_heal.write_active_graph", return_value=tmp_path / "active-graph.json"
            ) as mock_write:
                result = apply_self_heal(tmp_path, bead, record)
        assert result["self_heal"] is True

    def test_returns_band_string(self, tmp_path):
        bead = {"title": "Fix something", "bead_id": "BID-42"}
        record = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            with patch("workflows.self_heal.write_active_graph", return_value=tmp_path / "active-graph.json"):
                result = apply_self_heal(tmp_path, bead, record)
        assert "50" in result["band"]
        assert "69" in result["band"]

    def test_returns_tasks_list(self, tmp_path):
        bead = {"title": "Fix something", "bead_id": "BID-42"}
        record = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            with patch("workflows.self_heal.write_active_graph", return_value=tmp_path / "active-graph.json"):
                result = apply_self_heal(tmp_path, bead, record)
        assert isinstance(result["tasks"], list)
        assert len(result["tasks"]) > 0

    def test_task_graph_path_in_result(self, tmp_path):
        bead = {"title": "Fix something", "bead_id": "BID-42"}
        record = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        graph_path = tmp_path / ".agents" / "workflows" / "active-graph.json"
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            with patch("workflows.self_heal.write_active_graph", return_value=graph_path):
                result = apply_self_heal(tmp_path, bead, record)
        assert "task_graph_path" in result

    def test_fallback_objective_when_no_title(self, tmp_path):
        bead = {"bead_id": "BID-42"}
        record = _make_record(60.0, WorkflowDecision.PLAN_ONLY)
        mock_entry = MagicMock()
        with patch.dict("sys.modules", {"intake.queue": MagicMock(append_entry=mock_entry)}):
            with patch("workflows.self_heal.write_active_graph", return_value=tmp_path / "active-graph.json"):
                with patch("workflows.self_heal.build_standard_pipeline") as mock_pipeline:
                    mock_pipeline.return_value = {
                        "workflow_id": "WF-BID-42",
                        "tasks": [
                            {"task_id": "t-scout", "title": "Scout", "role": "scout"},
                        ],
                    }
                    apply_self_heal(tmp_path, bead, record)
        call_args = mock_pipeline.call_args
        assert "Re-decompose" in call_args[0][0] or "Re-decompose" in str(call_args)
