"""Tests for Gap B: ContextPressureMagnet deterministic compaction trigger."""

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.context_pressure_magnet import (  # noqa: E402
    ACTION_CHECKPOINT,
    ACTION_HOLD,
    ACTION_NOW,
    ContextPressureMagnet,
)
from magnets.plugin import default_registry  # noqa: E402

_M = ContextPressureMagnet()


def _obs(signal, ip="phase_boundary"):
    return _M.observe("CHR-T", ip, signal)


class TestBands:
    def test_below_soft_holds(self):
        ev = _obs({"context_pct": 30})
        assert ev.recommended_action == ACTION_HOLD
        assert ev.risk_delta == 0.0

    def test_soft_band_checkpoints(self):
        ev = _obs({"context_pct": 55})
        assert ev.recommended_action == ACTION_CHECKPOINT
        assert ev.risk_delta > 0

    def test_hard_band_compacts_now(self):
        ev = _obs({"context_pct": 85})
        assert ev.recommended_action == ACTION_NOW
        assert ev.risk_delta >= 0.4

    def test_custom_thresholds(self):
        ev = _obs({"context_pct": 66, "soft_pct": 65, "hard_pct": 90})
        assert ev.recommended_action == ACTION_CHECKPOINT


class TestTokenDerivation:
    def test_used_over_window(self):
        ev = _obs({"used_tokens": 90000, "window_tokens": 100000})
        assert ev.recommended_action == ACTION_NOW
        assert ev.observed_signal["context_pct"] == 90.0

    def test_zero_window_is_unknown(self):
        ev = _obs({"used_tokens": 10, "window_tokens": 0})
        assert ev.recommended_action == "none"


class TestGuards:
    def test_inactive_inflection_is_noop(self):
        ev = _obs({"context_pct": 99}, ip="intake")
        assert ev.recommended_action == "none"

    def test_missing_signal_is_noop(self):
        ev = _obs({})
        assert ev.recommended_action == "none"

    def test_never_raises_on_garbage(self):
        ev = _obs({"context_pct": "not-a-number"})
        assert ev.recommended_action == "none"


def test_registered_in_default_registry():
    assert "context_pressure_magnet" in default_registry().names()
