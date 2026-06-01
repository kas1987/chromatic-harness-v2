"""Tests for scripts/drift_gate.py (bead gh-61).

Network-free; uses tmp_path / monkeypatch for ARTIFACT_DIR + REPO.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# helpers to reload module with patched constants
# ---------------------------------------------------------------------------


def _load(monkeypatch, repo: Path, artifact_dir: Path):
    """Import drift_gate with env-patched REPO + ARTIFACT_DIR."""
    monkeypatch.setenv("DRIFT_GATE_REPO", str(repo))
    monkeypatch.setenv("DRIFT_GATE_ARTIFACT_DIR", str(artifact_dir))
    # Force re-import so module-level constants pick up the env vars.
    if "drift_gate" in sys.modules:
        del sys.modules["drift_gate"]
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import drift_gate  # noqa: PLC0415

    return drift_gate


# ---------------------------------------------------------------------------
# 1. compute_drift_score -- perfect
# ---------------------------------------------------------------------------


def test_compute_drift_score_perfect():
    from scripts.drift_gate import compute_drift_score

    assert compute_drift_score([], [], []) == 100


def test_compute_drift_score_missing_penalty():
    from scripts.drift_gate import compute_drift_score

    # 2 missing = -30
    score = compute_drift_score(["a", "b"], [], [])
    assert score == 70


def test_compute_drift_score_added_removed():
    from scripts.drift_gate import compute_drift_score

    # 1 added (-3) + 2 removed (-10) = -13
    score = compute_drift_score([], ["x"], ["y", "z"])
    assert score == 87


def test_compute_drift_score_floor_zero():
    from scripts.drift_gate import compute_drift_score

    # Many missing should clamp to 0
    score = compute_drift_score(["a"] * 10, ["b"] * 10, ["c"] * 10)
    assert score == 0


# ---------------------------------------------------------------------------
# 2. classify_trend
# ---------------------------------------------------------------------------


def test_classify_trend_improving():
    from scripts.drift_gate import classify_trend

    assert classify_trend([80.0, 90.0]) == "improving"


def test_classify_trend_worsening():
    from scripts.drift_gate import classify_trend

    assert classify_trend([90.0, 70.0]) == "worsening"


def test_classify_trend_stable():
    from scripts.drift_gate import classify_trend

    assert classify_trend([85.0, 85.0]) == "stable"


def test_classify_trend_single_entry():
    from scripts.drift_gate import classify_trend

    assert classify_trend([100.0]) == "stable"


def test_classify_trend_empty():
    from scripts.drift_gate import classify_trend

    assert classify_trend([]) == "stable"


# ---------------------------------------------------------------------------
# 3. protected path validation
# ---------------------------------------------------------------------------


def _make_protected_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with all protected paths present."""
    (tmp_path / ".github").mkdir()
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
    hooks_dir = tmp_path / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    router_dir = tmp_path / "02_RUNTIME" / "router"
    router_dir.mkdir(parents=True)
    (router_dir / "gate.py").write_text("", encoding="utf-8")
    (tmp_path / "AGENT_OPERATIONS.md").write_text("", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    return tmp_path


def test_protected_path_validation_pass(tmp_path):
    from scripts.drift_gate import validate_protected_paths

    repo = _make_protected_repo(tmp_path)
    result = validate_protected_paths(repo)
    assert result["passed"] is True
    assert result["missing"] == []


def test_protected_path_validation_fail(tmp_path):
    from scripts.drift_gate import validate_protected_paths

    # Do NOT create .github or CLAUDE.md
    result = validate_protected_paths(tmp_path)
    assert result["passed"] is False
    assert ".github" in result["missing"]
    assert "CLAUDE.md" in result["missing"]


# ---------------------------------------------------------------------------
# 4. remediation recommendations present
# ---------------------------------------------------------------------------


def test_build_recommendations_present():
    from scripts.drift_gate import build_recommendations

    recs = build_recommendations(
        missing_required=["docs"],
        added=["scratch"],
        removed=["tests"],
        missing_protected=[".github"],
    )
    assert any("docs" in r for r in recs)
    assert any("scratch" in r for r in recs)
    assert any("tests" in r for r in recs)
    assert any(".github" in r for r in recs)
    assert len(recs) == 4


# ---------------------------------------------------------------------------
# 5. no-baseline: records baseline and passes
# ---------------------------------------------------------------------------


def test_no_baseline_records_and_passes(tmp_path, monkeypatch):
    repo = _make_protected_repo(tmp_path)
    artifact_dir = tmp_path / "artifacts"
    dg = _load(monkeypatch, repo, artifact_dir)

    result = dg.run_gate(repo, "20260601T000000Z")

    assert result["passed"] is True
    assert (artifact_dir / "baseline.json").exists()
    assert result["drift"]["status"] == "baseline_created"


# ---------------------------------------------------------------------------
# 6. artifact write
# ---------------------------------------------------------------------------


def test_write_artifact(tmp_path, monkeypatch):
    repo = _make_protected_repo(tmp_path)
    artifact_dir = tmp_path / "artifacts"
    dg = _load(monkeypatch, repo, artifact_dir)

    result = dg.run_gate(repo, "20260601T010000Z")
    artifact = dg.write_artifact(result, "20260601T010000Z")

    assert artifact.exists()
    assert (artifact_dir / "latest.json").exists()
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert "score" in data
    assert "passed" in data


# ---------------------------------------------------------------------------
# 7. history append
# ---------------------------------------------------------------------------


def test_history_append(tmp_path, monkeypatch):
    repo = _make_protected_repo(tmp_path)
    artifact_dir = tmp_path / "artifacts"
    dg = _load(monkeypatch, repo, artifact_dir)

    dg.run_gate(repo, "20260601T010000Z")
    dg.run_gate(repo, "20260601T020000Z")

    history_file = artifact_dir / "history.jsonl"
    assert history_file.exists()
    lines = [l for l in history_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 2
    for line in lines:
        entry = json.loads(line)
        assert "timestamp" in entry
        assert "score" in entry


# ---------------------------------------------------------------------------
# 8. summarize fail-open (no latest.json)
# ---------------------------------------------------------------------------


def test_summarize_failopen_no_file(tmp_path, monkeypatch):
    repo = _make_protected_repo(tmp_path)
    artifact_dir = tmp_path / "artifacts_empty"
    dg = _load(monkeypatch, repo, artifact_dir)

    result = dg.summarize()
    assert result["status"] == "no_scan"
    assert result["passed"] is None


def test_summarize_returns_expected_keys(tmp_path, monkeypatch):
    repo = _make_protected_repo(tmp_path)
    artifact_dir = tmp_path / "artifacts"
    dg = _load(monkeypatch, repo, artifact_dir)

    gate_result = dg.run_gate(repo, "20260601T030000Z")
    dg.write_artifact(gate_result, "20260601T030000Z")

    summary = dg.summarize()
    assert summary["status"] == "ok"
    assert "passed" in summary
    assert "score" in summary
    assert "trend" in summary
    assert "missing_count" in summary
