"""Tests for 02_RUNTIME/workflows/verifier.py"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading via importlib so the test file is self-contained.
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_RUNTIME = _REPO / "02_RUNTIME"

# Ensure workflows.models is importable before loading verifier
for _p in (str(_REPO), str(_RUNTIME)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_models = _load("workflows.models", _RUNTIME / "workflows" / "models.py")
_verifier = _load("workflows.verifier", _RUNTIME / "workflows" / "verifier.py")

TaskNode = _models.TaskNode
VerifierResult = _models.VerifierResult
verify_task_completion = _verifier.verify_task_completion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**overrides) -> TaskNode:
    defaults = dict(
        task_id="T-001",
        title="Write unit tests",
        assigned_model="sonnet",
        role="engineer",
        tool_budget=10,
        confidence_required=75,
        risk_level="low",
        status="pending",
        allowed_files=[],
        forbidden_files=[],
        acceptance_criteria=[],
    )
    defaults.update(overrides)
    return TaskNode(**defaults)


# ---------------------------------------------------------------------------
# TestVerifier
# ---------------------------------------------------------------------------

class TestVerifier:

    def test_approve_clean_task(self):
        """All constraints satisfied → decision is approve."""
        task = _task()
        result = verify_task_completion(
            task,
            files_touched=["src/foo.py"],
            confidence_score=0.85,
            risk_level="low",
            tools_used=5,
        )
        assert result.decision == "approve"
        assert result.issues == []

    def test_reject_zero_confidence(self):
        """confidence_score <= 0 adds an issue."""
        task = _task()
        result = verify_task_completion(
            task,
            files_touched=[],
            confidence_score=0.0,
            risk_level="low",
            tools_used=1,
        )
        assert result.decision == "request_changes"
        assert any("confidence" in i for i in result.issues)

    def test_reject_tool_budget_exceeded(self):
        """tools_used > task.tool_budget adds an issue."""
        task = _task(tool_budget=5)
        result = verify_task_completion(
            task,
            files_touched=[],
            confidence_score=0.9,
            risk_level="medium",
            tools_used=6,
        )
        assert result.decision == "request_changes"
        assert any("budget" in i for i in result.issues)

    def test_reject_human_gate_bypass(self):
        """human_gate_bypassed=True triggers a 'reject' (not just request_changes)."""
        task = _task()
        result = verify_task_completion(
            task,
            files_touched=[],
            confidence_score=0.8,
            risk_level="low",
            tools_used=2,
            human_gate_bypassed=True,
        )
        assert result.decision == "reject"
        assert any("bypass" in i for i in result.issues)

    def test_reject_forbidden_file_touched(self):
        """Touching a forbidden file forces decision=reject."""
        task = _task(forbidden_files=["secrets/.env"])
        result = verify_task_completion(
            task,
            files_touched=["secrets/.env"],
            confidence_score=0.9,
            risk_level="low",
            tools_used=1,
        )
        assert result.decision == "reject"
        assert any("forbidden" in i for i in result.issues)

    def test_reject_file_outside_scope(self):
        """File not in allowed_files (when allowed_files is set) causes an issue."""
        task = _task(allowed_files=["src/allowed.py"])
        result = verify_task_completion(
            task,
            files_touched=["src/not_allowed.py"],
            confidence_score=0.9,
            risk_level="low",
            tools_used=1,
        )
        assert result.decision == "request_changes"
        assert any("outside scope" in i for i in result.issues)

    def test_file_under_allowed_prefix_passes(self):
        """A file under an allowed directory prefix should not be flagged."""
        task = _task(allowed_files=["src/"])
        result = verify_task_completion(
            task,
            files_touched=["src/sub/module.py"],
            confidence_score=0.9,
            risk_level="low",
            tools_used=1,
        )
        assert result.decision == "approve"

    def test_validation_required_but_missing(self):
        """acceptance_criteria present but validation='' adds an issue."""
        task = _task(acceptance_criteria=["all tests pass"])
        result = verify_task_completion(
            task,
            files_touched=[],
            confidence_score=0.9,
            risk_level="low",
            tools_used=1,
            validation="",
        )
        assert result.decision == "request_changes"
        assert any("validation" in i for i in result.issues)

    def test_result_carries_task_id_and_verifier(self):
        """VerifierResult is properly populated with task_id and verifier name."""
        task = _task(task_id="T-XYZ")
        result = verify_task_completion(
            task,
            files_touched=[],
            confidence_score=0.9,
            risk_level="medium",
            tools_used=2,
            verifier="opus",
        )
        assert result.task_id == "T-XYZ"
        assert result.verifier == "opus"

    def test_missing_risk_level_flags_issue(self):
        """Empty risk_level string adds a missing-risk-level issue."""
        task = _task()
        result = verify_task_completion(
            task,
            files_touched=[],
            confidence_score=0.8,
            risk_level="",
            tools_used=1,
        )
        assert result.decision == "request_changes"
        assert any("risk" in i for i in result.issues)
