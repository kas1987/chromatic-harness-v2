"""Tests for calibrate_e1_threshold.py — metrics, rebalance decisions, audit writes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import scripts.calibrate_e1_threshold as cal


def _make_report(
    items: list[dict] | None = None,
    e0_counts: dict | None = None,
    e1_counts: dict | None = None,
) -> dict:
    e0 = e0_counts or {"N1": 0, "N2": 0, "N3": 5, "N4": 10}
    e1 = e1_counts or {"N1": 0, "N2": 0, "N3": 0, "N4": 0}
    return {
        "generated_at_utc": "2026-05-30T00:00:00Z",
        "pyramid": {"E0": e0, "E1": e1, "E2": {}, "E3": {}, "E4": {}},
        "items": items or [],
    }


def _make_policy(e1_min_score: float = 0.32) -> dict:
    return {
        "tiers": {
            "E1": {
                "min_score": e1_min_score,
                "min_uses": 2,
                "min_weeks": 1,
                "min_breadth": 1,
                "max_failure_rate": 0.35,
            }
        }
    }


# --- _compute_metrics ---


def test_compute_metrics_graduation_rate_zero_when_no_e1() -> None:
    report = _make_report()
    policy = _make_policy()
    m = cal._compute_metrics(report, policy)
    assert m["graduation_rate"] == 0.0
    assert m["e0_total"] == 15
    assert m["e1_total"] == 0


def test_compute_metrics_graduation_rate_with_e1() -> None:
    report = _make_report(
        e0_counts={"N1": 0, "N2": 0, "N3": 8, "N4": 0},
        e1_counts={"N1": 2, "N2": 0, "N3": 0, "N4": 0},
    )
    policy = _make_policy()
    m = cal._compute_metrics(report, policy)
    assert m["e0_total"] == 8
    assert m["e1_total"] == 2
    assert m["graduation_rate"] == pytest.approx(0.2, abs=0.001)


def test_compute_metrics_near_e1_count() -> None:
    items = [
        {"evidence_tier": "E0", "score": 0.30},  # within window (0.32 - 0.05 = 0.27)
        {"evidence_tier": "E0", "score": 0.28},  # within window
        {"evidence_tier": "E0", "score": 0.15},  # outside window
        {"evidence_tier": "E1", "score": 0.35},  # E1, not counted
    ]
    report = _make_report(items=items)
    policy = _make_policy(e1_min_score=0.32)
    m = cal._compute_metrics(report, policy)
    assert m["near_e1_count"] == 2


def test_compute_metrics_near_e1_excludes_above_threshold() -> None:
    items = [
        {"evidence_tier": "E0", "score": 0.33},  # above threshold — not near-E1
        {"evidence_tier": "E0", "score": 0.30},  # within window
    ]
    report = _make_report(items=items)
    policy = _make_policy(e1_min_score=0.32)
    m = cal._compute_metrics(report, policy)
    assert m["near_e1_count"] == 1


# --- _decide_rebalance ---


def test_decide_rebalance_lower_when_graduation_low_and_near_e1_high() -> None:
    metrics = {
        "graduation_rate": 0.02,  # < 0.05
        "near_e1_count": 5,  # >= 3
        "e1_min_score": 0.32,
    }
    decision, rationale, new_threshold = cal._decide_rebalance(metrics)
    assert decision == "LOWER"
    assert new_threshold == pytest.approx(0.30, abs=0.001)
    assert "stranded" in rationale


def test_decide_rebalance_no_change_when_near_e1_too_low() -> None:
    metrics = {
        "graduation_rate": 0.02,
        "near_e1_count": 1,  # < 3, so no LOWER despite low graduation
        "e1_min_score": 0.32,
    }
    decision, _, _ = cal._decide_rebalance(metrics)
    assert decision == "NO_CHANGE"


def test_decide_rebalance_raise_when_graduation_high() -> None:
    metrics = {
        "graduation_rate": 0.40,  # > 0.30
        "near_e1_count": 10,
        "e1_min_score": 0.32,
    }
    decision, rationale, new_threshold = cal._decide_rebalance(metrics)
    assert decision == "RAISE"
    assert new_threshold == pytest.approx(0.34, abs=0.001)
    assert "permissive" in rationale


def test_decide_rebalance_floor_enforced() -> None:
    metrics = {
        "graduation_rate": 0.01,
        "near_e1_count": 5,
        "e1_min_score": 0.28,  # already at floor
    }
    decision, _, new_threshold = cal._decide_rebalance(metrics)
    assert decision == "NO_CHANGE"
    assert new_threshold == pytest.approx(0.28, abs=0.001)


def test_decide_rebalance_ceiling_enforced() -> None:
    metrics = {
        "graduation_rate": 0.50,
        "near_e1_count": 0,
        "e1_min_score": 0.45,  # already at ceiling
    }
    decision, _, new_threshold = cal._decide_rebalance(metrics)
    assert decision == "NO_CHANGE"
    assert new_threshold == pytest.approx(0.45, abs=0.001)


def test_decide_rebalance_no_change_within_band() -> None:
    metrics = {
        "graduation_rate": 0.15,  # between 0.05 and 0.30
        "near_e1_count": 2,
        "e1_min_score": 0.32,
    }
    decision, _, new_threshold = cal._decide_rebalance(metrics)
    assert decision == "NO_CHANGE"
    assert new_threshold == pytest.approx(0.32, abs=0.001)


# --- _write_audit ---


def test_write_audit_creates_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cal, "CYCLES_DIR", tmp_path / "calibration-cycles")
    metrics = {
        "e1_min_score": 0.32,
        "graduation_rate": 0.02,
        "near_e1_count": 5,
        "e0_total": 60,
        "e1_total": 0,
        "avg_score_e0": 0.18,
    }
    path = cal._write_audit(
        3, "2026-05-30", metrics, "LOWER", "test rationale", 0.30, dry_run=False
    )
    assert path.is_file()
    artifact = json.loads(path.read_text())
    assert artifact["cycle_number"] == 3
    assert artifact["decision"] == "LOWER"
    assert artifact["before_threshold"] == pytest.approx(0.32)
    assert artifact["after_threshold"] == pytest.approx(0.30)
    assert artifact["dry_run"] is False


def test_write_audit_dry_run_does_not_create_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cal, "CYCLES_DIR", tmp_path / "calibration-cycles")
    metrics = {
        "e1_min_score": 0.32,
        "graduation_rate": 0.02,
        "near_e1_count": 5,
        "e0_total": 60,
        "e1_total": 0,
        "avg_score_e0": 0.18,
    }
    path = cal._write_audit(
        1, "2026-05-30", metrics, "NO_CHANGE", "dry run", 0.32, dry_run=True
    )
    assert not path.is_file()


# --- _apply_threshold ---


def test_apply_threshold_writes_updated_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy_file = tmp_path / "learning_tier_policy.json"
    policy = _make_policy(e1_min_score=0.32)
    policy_file.write_text(json.dumps(policy))
    monkeypatch.setattr(cal, "POLICY_PATH", policy_file)

    cal._apply_threshold(policy, 0.30)

    updated = json.loads(policy_file.read_text())
    assert updated["tiers"]["E1"]["min_score"] == pytest.approx(0.30)
