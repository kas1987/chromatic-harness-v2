"""Tests for test pyramid analysis."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.test_pyramid import analyze_test_pyramid, classify_test  # noqa: E402


def _tests(names: list[str]) -> list[dict]:
    return [{"test_name": n, "status": "pass", "duration_ms": 10} for n in names]


def test_classify_layers():
    assert classify_test({"test_name": "test_user_model"}) == "unit"
    assert classify_test({"test_name": "api_integration_check"}) == "integration"
    assert classify_test({"test_name": "checkout_e2e_flow"}) == "e2e"
    assert classify_test({"test_name": "x", "layer": "unit"}) == "unit"


def test_balanced_pyramid_no_warnings():
    names = [f"unit_test_{i}" for i in range(7)]
    names += ["api_integration_smoke", "api_integration_db"]
    names += ["login_e2e"]
    report = analyze_test_pyramid(_tests(names))
    assert report["total"] == 10
    assert report["balanced"] is True
    assert report["warnings"] == []


def test_inverted_pyramid_warns():
    names = ["e2e_a", "e2e_b", "e2e_c", "e2e_d", "integration_x"]
    report = analyze_test_pyramid(_tests(names))
    assert not report["balanced"]
    assert any("inverted" in w or "imbalance" in w for w in report["warnings"])


def test_confidence_magnet_observes_pyramid():
    from magnets.confidence_magnet import ConfidenceMagnet

    magnet = ConfidenceMagnet()
    event = magnet.observe(
        "CHR-PYRAMID",
        "test_results",
        {
            "tests": _tests(["e2e_1", "e2e_2", "e2e_3", "integration_a"]),
            "confidence_delta": 0.1,
        },
    )
    assert event.magnet_name == "confidence_magnet"
    assert any("pyramid" in ev.lower() for ev in event.evidence)
    assert event.confidence_delta < 0.1
