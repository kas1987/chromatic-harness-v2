"""Tests for scripts/agent_scoring.py (bead gh-63). Network-free."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import agent_scoring as ag


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_EVENTS = [
    {"agent": "alpha", "outcome": "completed", "confidence": 0.9, "false_positive": False},
    {"agent": "alpha", "outcome": "completed", "confidence": 0.8, "false_positive": True},
    {"agent": "alpha", "outcome": "failed", "confidence": 0.5, "false_positive": False},
    {"agent": "beta", "outcome": "completed", "confidence": 1.0, "false_positive": False},
    {"agent": "beta", "outcome": "completed", "confidence": 1.0, "false_positive": False},
]


# ---------------------------------------------------------------------------
# build_scorecard
# ---------------------------------------------------------------------------


def test_build_scorecard_multi_agent():
    card = ag.build_scorecard(SAMPLE_EVENTS)
    assert set(card.keys()) == {"alpha", "beta"}


def test_build_scorecard_alpha_aggregates():
    card = ag.build_scorecard(SAMPLE_EVENTS)
    a = card["alpha"]
    assert a["tasks"] == 3
    assert a["completed"] == 2
    assert a["failed"] == 1
    assert round(a["completion_rate"], 4) == round(2 / 3, 4)
    assert round(a["failure_rate"], 4) == round(1 / 3, 4)


def test_build_scorecard_avg_confidence():
    card = ag.build_scorecard(SAMPLE_EVENTS)
    a = card["alpha"]
    expected = round((0.9 + 0.8 + 0.5) / 3, 4)
    assert a["avg_confidence"] == expected


# ---------------------------------------------------------------------------
# False-positive tracking
# ---------------------------------------------------------------------------


def test_false_positive_count_and_rate():
    card = ag.build_scorecard(SAMPLE_EVENTS)
    a = card["alpha"]
    assert a["false_positive_count"] == 1
    assert round(a["false_positive_rate"], 4) == round(1 / 3, 4)


def test_false_positive_zero_for_beta():
    card = ag.build_scorecard(SAMPLE_EVENTS)
    assert card["beta"]["false_positive_count"] == 0
    assert card["beta"]["false_positive_rate"] == 0.0


# ---------------------------------------------------------------------------
# performance_score
# ---------------------------------------------------------------------------


def test_performance_score_perfect():
    card = {
        "completion_rate": 1.0,
        "avg_confidence": 1.0,
        "false_positive_rate": 0.0,
    }
    assert ag.performance_score(card) == 100


def test_performance_score_poor():
    card = {
        "completion_rate": 0.0,
        "avg_confidence": 0.0,
        "false_positive_rate": 1.0,
    }
    assert ag.performance_score(card) == 0


def test_performance_score_range():
    card = ag.build_scorecard(SAMPLE_EVENTS)["alpha"]
    score = ag.performance_score(card)
    assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# classify_trend
# ---------------------------------------------------------------------------


def test_classify_trend_improving():
    assert ag.classify_trend([50.0, 60.0, 70.0]) == "improving"


def test_classify_trend_worsening():
    assert ag.classify_trend([80.0, 70.0]) == "worsening"


def test_classify_trend_stable_equal():
    assert ag.classify_trend([70.0, 70.0]) == "stable"


def test_classify_trend_stable_single():
    assert ag.classify_trend([70.0]) == "stable"


def test_classify_trend_empty():
    assert ag.classify_trend([]) == "stable"


# ---------------------------------------------------------------------------
# History append
# ---------------------------------------------------------------------------


def test_history_append(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(ag, "HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(ag, "LATEST_FILE", tmp_path / "latest.json")
    monkeypatch.setattr(ag, "DASHBOARD_FILE", tmp_path / "dashboard.md")

    ag.run_scoring(SAMPLE_EVENTS, "20260601T000000Z")
    ag.run_scoring(SAMPLE_EVENTS, "20260601T010000Z")

    lines = (tmp_path / "history.jsonl").read_text().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert "timestamp" in entry
    assert "scores" in entry
    assert "alpha" in entry["scores"]


# ---------------------------------------------------------------------------
# Dashboard written
# ---------------------------------------------------------------------------


def test_dashboard_written(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(ag, "HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(ag, "LATEST_FILE", tmp_path / "latest.json")
    monkeypatch.setattr(ag, "DASHBOARD_FILE", tmp_path / "dashboard.md")

    ag.run_scoring(SAMPLE_EVENTS, "20260601T000000Z")

    dashboard = (tmp_path / "dashboard.md").read_text()
    assert "Agent Performance Dashboard" in dashboard
    assert "alpha" in dashboard
    assert "beta" in dashboard
    assert "|" in dashboard  # table present


# ---------------------------------------------------------------------------
# summarize fail-open
# ---------------------------------------------------------------------------


def test_summarize_no_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "LATEST_FILE", tmp_path / "latest.json")
    result = ag.summarize()
    assert result["status"] == "no_scan"
    assert result["top_agent"] is None


def test_summarize_with_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(ag, "HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(ag, "LATEST_FILE", tmp_path / "latest.json")
    monkeypatch.setattr(ag, "DASHBOARD_FILE", tmp_path / "dashboard.md")

    ag.run_scoring(SAMPLE_EVENTS, "20260601T000000Z")
    result = ag.summarize()
    assert result["status"] == "ok"
    assert result["agents"] == 2
    assert result["top_agent"] in {"alpha", "beta"}
    assert result["lowest_agent"] in {"alpha", "beta"}


def test_summarize_corrupt_artifact(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text("not json")
    monkeypatch.setattr(ag, "LATEST_FILE", latest)
    result = ag.summarize()
    # must not raise; status reflects error or no data
    assert "status" in result


# ---------------------------------------------------------------------------
# Artifact write
# ---------------------------------------------------------------------------


def test_write_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(ag, "LATEST_FILE", tmp_path / "latest.json")

    card = ag.build_scorecard(SAMPLE_EVENTS)
    scores = {a: ag.performance_score(c) for a, c in card.items()}
    path = ag.write_artifact(card, scores, "20260601T000000Z")

    assert path.exists()
    data = json.loads(path.read_text())
    assert "scorecard" in data
    assert "scores" in data


# ---------------------------------------------------------------------------
# Empty events
# ---------------------------------------------------------------------------


def test_empty_events():
    card = ag.build_scorecard([])
    assert card == {}


def test_run_scoring_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ag, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(ag, "HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(ag, "LATEST_FILE", tmp_path / "latest.json")
    monkeypatch.setattr(ag, "DASHBOARD_FILE", tmp_path / "dashboard.md")

    result = ag.run_scoring([], "20260601T000000Z")
    assert result["scorecard"] == {}
    assert result["scores"] == {}
