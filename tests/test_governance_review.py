"""Tests for governance_review.py orchestrator (gh-geov).

Network-free: git diff via ai_review_gate fails open to a clean diff; no bd/GH
calls are exercised. Pure synthesis + composition + artifact contract.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_synthesize_reviews_maps_block_and_fail_to_reject():
    mod = _load("governance_review")
    reviews = mod.synthesize_reviews(
        {"decision": "block", "violations": [{"id": "x"}]},
        {"level": "fail", "risk_score": 90, "findings": [{"rule": "r"}]},
    )
    by = {r["reviewer"]: r for r in reviews}
    assert by["policy_engine"]["verdict"] == "reject"
    assert by["ai_review_gate"]["verdict"] == "reject"
    # confidence is in valid range and ascii-safe notes
    for r in reviews:
        assert 0.0 <= r["confidence"] <= 1.0
        r["notes"].encode("ascii")


def test_synthesize_reviews_clean_signal_approves():
    mod = _load("governance_review")
    reviews = mod.synthesize_reviews(
        {"decision": "allow", "violations": []},
        {"level": "ok", "risk_score": 0, "findings": []},
    )
    verdicts = {r["verdict"] for r in reviews}
    assert verdicts == {"approve"}


def test_synthesize_reviews_warn_is_abstain():
    mod = _load("governance_review")
    reviews = mod.synthesize_reviews(
        {"decision": "allow", "violations": []},
        {"level": "warn", "risk_score": 40, "findings": []},
    )
    ai = next(r for r in reviews if r["reviewer"] == "ai_review_gate")
    assert ai["verdict"] == "abstain"


def test_run_review_clean_diff_allows(monkeypatch):
    mod = _load("governance_review")
    # Force a clean AI review + allow policy so the path is deterministic.
    monkeypatch.setattr(
        mod, "run_ai_review_stage", lambda base: {"risk_score": 0, "level": "ok", "findings": [], "changed_files": 0}
    )
    monkeypatch.setattr(mod, "run_policy_stage", lambda ctx: {"decision": "allow", "violations": [], "by_severity": {}})
    result = mod.run_review("origin/main")
    assert result["decision"] == "allow"
    assert result["consensus"]["final_decision"] == "approve"


def test_run_review_policy_block_is_authoritative(monkeypatch):
    mod = _load("governance_review")
    monkeypatch.setattr(
        mod, "run_ai_review_stage", lambda base: {"risk_score": 0, "level": "ok", "findings": [], "changed_files": 0}
    )
    monkeypatch.setattr(
        mod,
        "run_policy_stage",
        lambda ctx: {"decision": "block", "violations": [{"id": "v"}], "by_severity": {"block": 1}},
    )
    result = mod.run_review("origin/main")
    assert result["decision"] == "block"


def test_write_artifact_and_summarize_roundtrip(monkeypatch, tmp_path):
    mod = _load("governance_review")
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(mod, "LATEST_ARTIFACT", tmp_path / "latest.json")
    result = {
        "decision": "allow",
        "policy": {"decision": "allow"},
        "ai_review": {"level": "ok", "risk_score": 0},
        "consensus": {"final_decision": "approve"},
    }
    path = mod.write_artifact(result, "20260601T000000Z")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["timestamp"] == "20260601T000000Z"
    s = mod.summarize()
    assert s["status"] == "ok"
    assert s["decision"] == "allow"
    assert s["final_decision"] == "approve"


def test_summarize_no_scan_is_fail_open(monkeypatch, tmp_path):
    mod = _load("governance_review")
    monkeypatch.setattr(mod, "LATEST_ARTIFACT", tmp_path / "nope.json")
    s = mod.summarize()
    assert s["status"] == "no_scan"
    assert s["decision"] is None


def test_release_readiness_blocks_on_governance_block():
    mod = _load("release_readiness")
    assert "governance_review" in mod._ARTIFACT_PATHS
    inputs = {"governance_review": {"decision": "block"}}
    blockers = mod.collect_blockers(inputs)
    assert any(b["gate"] == "governance_review" for b in blockers)


if __name__ == "__main__":
    import pytest
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
