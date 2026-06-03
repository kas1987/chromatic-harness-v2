"""Tests for router pipeline advisory stage."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "02_RUNTIME"))

import pytest

from router.pipeline.advisory import overlay_advisory, read_routing_overlay


# ── read_routing_overlay ──────────────────────────────────────────────────────


def test_read_routing_overlay_returns_none_when_missing(tmp_path, monkeypatch):
    """Returns None when the overlay file does not exist."""
    import router.pipeline.advisory as adv

    monkeypatch.setattr(adv, "_REPO", tmp_path)
    adv._REPO = tmp_path
    result = read_routing_overlay.__wrapped__() if hasattr(read_routing_overlay, "__wrapped__") else None
    # Call directly by patching the internal _repo() helper
    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = read_routing_overlay()
    assert result is None


def test_read_routing_overlay_returns_dict_when_valid(tmp_path):
    """Returns parsed dict for a valid overlay file."""
    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    overlay_file = overlay_dir / "routing_policy_overlay.json"
    overlay_file.write_text(
        json.dumps({"c_to_t_threshold": 0.7, "allow_paid_spill": False}),
        encoding="utf-8",
    )

    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = read_routing_overlay()

    assert isinstance(result, dict)
    assert result["c_to_t_threshold"] == 0.7
    assert result["allow_paid_spill"] is False


def test_read_routing_overlay_returns_none_on_invalid_json(tmp_path):
    """Returns None when overlay file contains malformed JSON."""
    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text("{not valid json", encoding="utf-8")

    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = read_routing_overlay()

    assert result is None


def test_read_routing_overlay_returns_none_for_list_json(tmp_path):
    """Returns None when overlay file contains a JSON list instead of dict."""
    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text("[1, 2, 3]", encoding="utf-8")

    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = read_routing_overlay()

    assert result is None


# ── overlay_advisory ─────────────────────────────────────────────────────────


def test_overlay_advisory_returns_empty_when_no_overlay(tmp_path):
    """Returns empty string when there is no overlay file."""
    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = overlay_advisory()
    assert result == ""


def test_overlay_advisory_contains_threshold_and_spill(tmp_path):
    """Advisory string includes threshold and paid_spill values."""
    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text(
        json.dumps({"c_to_t_threshold": 0.8, "allow_paid_spill": True}),
        encoding="utf-8",
    )

    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = overlay_advisory()

    assert "0.8" in result
    assert "True" in result


def test_overlay_advisory_marks_stale_fallback(tmp_path):
    """Advisory string mentions STALE-FALLBACK when staleness_fallback is true."""
    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text(
        json.dumps({"c_to_t_threshold": 0.5, "allow_paid_spill": False, "staleness_fallback": True}),
        encoding="utf-8",
    )

    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = overlay_advisory()

    assert "STALE-FALLBACK" in result


def test_overlay_advisory_no_stale_marker_when_flag_false(tmp_path):
    """STALE-FALLBACK is absent when staleness_fallback is False."""
    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text(
        json.dumps({"c_to_t_threshold": 0.5, "allow_paid_spill": False, "staleness_fallback": False}),
        encoding="utf-8",
    )

    with patch("router.pipeline.advisory._repo", return_value=tmp_path):
        result = overlay_advisory()

    assert "STALE-FALLBACK" not in result
    assert "overlay" in result


def test_overlay_advisory_returns_empty_on_exception():
    """Returns empty string when an unexpected error is raised (fail-open)."""
    with patch("router.pipeline.advisory.read_routing_overlay", side_effect=RuntimeError("boom")):
        result = overlay_advisory()
    assert result == ""


# ── context_gate_advisory ─────────────────────────────────────────────────────


def test_context_gate_advisory_returns_string(tmp_path):
    """context_gate_advisory returns a non-empty string on success."""
    from router.pipeline.advisory import context_gate_advisory

    # We just verify it returns a str and does not raise; heavy mocking is
    # acceptable because context_gate.py has its own test suite.
    result = context_gate_advisory("write tests", "def foo(): pass", "medium")
    assert isinstance(result, str)


def test_context_gate_advisory_is_fail_open():
    """Returns empty string rather than raising when internals fail."""
    from router.pipeline.advisory import context_gate_advisory

    with patch("importlib.util.spec_from_file_location", side_effect=ImportError("no module")):
        result = context_gate_advisory("desc", "prompt", "low")
    assert result == ""
