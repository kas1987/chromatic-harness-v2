"""Tests for the multi-agent review-consensus engine (bead gh-65).

Network-free and deterministic: reviews are supplied as input dicts.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("review_consensus", REPO / "scripts" / "review_consensus.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# --- normalize_reviews ------------------------------------------------------


def test_normalize_valid_reviews():
    mod = _load()
    raw = [{"reviewer": "a", "verdict": "approve", "confidence": 0.8, "notes": "ok"}]
    out = mod.normalize_reviews(raw)
    assert out == [{"reviewer": "a", "verdict": "approve", "confidence": 0.8, "notes": "ok"}]


def test_normalize_invalid_verdict_becomes_abstain():
    mod = _load()
    out = mod.normalize_reviews([{"reviewer": "a", "verdict": "maybe", "confidence": 2.0}])
    assert out[0]["verdict"] == "abstain"
    assert out[0]["confidence"] == 1.0  # clamped to [0,1]


def test_normalize_drops_non_dicts_and_defaults():
    mod = _load()
    out = mod.normalize_reviews(["nope", 42, {"verdict": "reject"}])
    assert len(out) == 1
    assert out[0]["reviewer"].startswith("reviewer-")
    assert out[0]["confidence"] == 0.5  # bad/missing -> default
    assert out[0]["notes"] == ""


def test_normalize_non_list_returns_empty():
    mod = _load()
    assert mod.normalize_reviews({"not": "a list"}) == []


# --- compute_consensus ------------------------------------------------------


def test_consensus_unanimous_approve():
    mod = _load()
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.9},
            {"reviewer": "b", "verdict": "approve", "confidence": 0.7},
        ]
    )
    c = mod.compute_consensus(reviews)
    assert c["verdict"] == "approve"
    assert c["score"] == 1.0
    assert c["reject_weight"] == 0.0


def test_consensus_unanimous_reject():
    mod = _load()
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "reject", "confidence": 1.0},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.5},
        ]
    )
    c = mod.compute_consensus(reviews)
    assert c["verdict"] == "reject"
    assert c["score"] == -1.0


def test_consensus_weighted_by_confidence():
    mod = _load()
    # high-confidence approve should beat low-confidence reject
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.9},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.2},
        ]
    )
    c = mod.compute_consensus(reviews)
    assert c["verdict"] == "approve"
    assert c["score"] > 0


def test_consensus_abstains_ignored():
    mod = _load()
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.8},
            {"reviewer": "b", "verdict": "abstain", "confidence": 1.0},
        ]
    )
    c = mod.compute_consensus(reviews)
    assert c["approve_weight"] == 0.8
    assert c["reject_weight"] == 0.0
    assert c["verdict"] == "approve"


def test_consensus_tie_equal_weight():
    mod = _load()
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.6},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.6},
        ]
    )
    c = mod.compute_consensus(reviews)
    assert c["verdict"] == "tie"
    assert c["score"] == 0.0


def test_consensus_within_tie_band_is_tie():
    mod = _load()
    # slight approve lean but inside default 0.1 band -> tie
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.52},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.50},
        ]
    )
    c = mod.compute_consensus(reviews)
    assert abs(c["score"]) <= mod.CONSENSUS_TIE_BAND
    assert c["verdict"] == "tie"


# --- resolve_tie ------------------------------------------------------------


def test_resolve_tie_high_confidence_breaks():
    mod = _load()
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.9},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.9},
            {"reviewer": "c", "verdict": "approve", "confidence": 0.95},
        ]
    )
    c = mod.compute_consensus(reviews)
    # construct a true tie for the test by forcing tie verdict path
    tie = mod.resolve_tie({"verdict": "tie", "score": 0.0}, reviews)
    assert tie["escalation"] is False
    assert tie["tie_break_verdict"] == "approve"
    assert tie["tie_break_by"] == "c"


def test_resolve_tie_escalates_when_leaders_disagree():
    mod = _load()
    reviews = mod.normalize_reviews(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.9},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.9},
        ]
    )
    tie = mod.resolve_tie({"verdict": "tie", "score": 0.0}, reviews)
    assert tie["escalation"] is True
    assert tie["tie_break_verdict"] is None


def test_resolve_tie_escalates_when_all_abstain():
    mod = _load()
    reviews = mod.normalize_reviews([{"reviewer": "a", "verdict": "abstain", "confidence": 0.9}])
    tie = mod.resolve_tie({"verdict": "tie", "score": 0.0}, reviews)
    assert tie["escalation"] is True
    assert "no decisive" in tie["escalation_reason"]


def test_no_escalation_on_clear_verdict():
    mod = _load()
    tie = mod.resolve_tie({"verdict": "approve", "score": 0.8}, [])
    assert tie["escalation"] is False


# --- build_result + escalation requires human -------------------------------


def test_build_result_escalated_has_no_final_decision():
    mod = _load()
    result = mod.build_result(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.9},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.9},
        ]
    )
    assert result["escalation"] is True
    assert result["final_decision"] is None


# --- apply_human_approval ---------------------------------------------------


def test_apply_human_approval_finalizes_escalation():
    mod = _load()
    result = mod.build_result(
        [
            {"reviewer": "a", "verdict": "approve", "confidence": 0.9},
            {"reviewer": "b", "verdict": "reject", "confidence": 0.9},
        ]
    )
    assert result["final_decision"] is None
    mod.apply_human_approval(result, "alice", "approve")
    assert result["final_decision"] == "approve"
    assert result["escalation"] is False
    assert result["human_approval"]["approver"] == "alice"


def test_apply_human_approval_rejects_invalid_decision():
    mod = _load()
    result = mod.build_result([{"reviewer": "a", "verdict": "approve", "confidence": 0.9}])
    try:
        mod.apply_human_approval(result, "alice", "perhaps")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


# --- artifact + summarize ---------------------------------------------------


def test_write_artifact_and_summarize(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "review_consensus")
    result = mod.build_result([{"reviewer": "a", "verdict": "approve", "confidence": 0.9}])
    latest = mod.write_artifact(result, "20260601T000000Z")
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["final_decision"] == "approve"
    assert data["timestamp"] == "20260601T000000Z"

    s = mod.summarize()
    assert s["status"] == "ok"
    assert s["verdict"] == "approve"
    assert s["final_decision"] == "approve"
    assert set(s) >= {"status", "verdict", "score", "escalation", "final_decision"}


def test_summarize_fail_open_when_missing(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "absent")
    s = mod.summarize()
    assert s["status"] == "no_report"
    assert set(s) >= {"status", "verdict", "score", "escalation", "final_decision"}
