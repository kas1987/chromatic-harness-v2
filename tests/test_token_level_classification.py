"""Tests for token_level_inference.classify_event — gh4a bead coverage.

Covers:
  1. classify_event fills c_level/t_level from model name when missing/null.
  2. classify_event preserves existing non-null levels (router decisions win).
  3. classify_event handles nested cost_center model extraction via _classify_ledger_row
     helper in reset_budget_daily_from_ledger.
  4. classify_event is fail-open on bad input.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Ensure scripts/ is importable regardless of cwd.
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from token_level_inference import classify_event, infer_levels  # noqa: E402


# ---------------------------------------------------------------------------
# infer_levels unit tests
# ---------------------------------------------------------------------------


def test_infer_opus():
    c, t, conf = infer_levels("claude-opus-4-8")
    assert c == "C4"
    assert t == "T4"
    assert conf == "inferred"


def test_infer_sonnet():
    c, t, conf = infer_levels("claude-sonnet-4-6")
    assert c == "C3"
    assert t == "T3"
    assert conf == "inferred"


def test_infer_haiku():
    c, t, conf = infer_levels("claude-haiku-3")
    assert c == "C2"
    assert t == "T2"
    assert conf == "inferred"


def test_infer_unknown_model():
    c, t, conf = infer_levels("totally-unknown-model-xyz")
    assert c is None
    assert t is None
    assert conf == "unknown"


def test_infer_none():
    c, t, conf = infer_levels(None)
    assert c is None
    assert conf == "unknown"


# ---------------------------------------------------------------------------
# classify_event: fills levels from model name
# ---------------------------------------------------------------------------


def test_classify_event_fills_from_model():
    """Missing c_level/t_level are inferred from the model name."""
    event = {"model": "claude-opus-4-8", "c_level": None, "t_level": None, "confidence": "unknown"}
    result = classify_event(event)
    assert result["c_level"] == "C4"
    assert result["t_level"] == "T4"
    assert result["confidence"] == "inferred"


def test_classify_event_fills_from_model_name_alias():
    """model_name field is also accepted."""
    event = {"model_name": "claude-sonnet-4-6", "c_level": None, "t_level": None}
    result = classify_event(event)
    assert result["c_level"] == "C3"
    assert result["t_level"] == "T3"


def test_classify_event_preserves_existing_levels():
    """Router decision levels (non-null) are never overwritten."""
    event = {
        "model": "claude-opus-4-8",
        "c_level": "C2",  # deliberately wrong — router said C2
        "t_level": "T2",
        "confidence": "router",
    }
    result = classify_event(event)
    assert result["c_level"] == "C2", "router-set c_level must be preserved"
    assert result["t_level"] == "T2", "router-set t_level must be preserved"
    assert result["confidence"] == "router"


def test_classify_event_preserves_partial_existing_level():
    """If only c_level is set, t_level is inferred but c_level kept."""
    event = {"model": "claude-haiku-3", "c_level": "C4", "t_level": None}
    result = classify_event(event)
    assert result["c_level"] == "C4", "existing c_level must be preserved"
    assert result["t_level"] == "T2", "missing t_level should be inferred"


def test_classify_event_unknown_model_no_change():
    """Unknown model leaves levels as-is (still None)."""
    event = {"model": "unknown-model-xyz", "c_level": None, "t_level": None, "confidence": "unknown"}
    result = classify_event(event)
    assert result["c_level"] is None
    assert result["t_level"] is None
    assert result["confidence"] == "unknown"


def test_classify_event_fail_open_on_bad_input():
    """Bad/non-dict input returns the original without raising."""
    # Pass a non-dict; classify_event wraps in try/except and returns input.
    bad = "not-a-dict"
    result = classify_event(bad)  # type: ignore[arg-type]
    assert result == bad


def test_classify_event_empty_string_model():
    """Empty model string returns unchanged event."""
    event = {"model": "", "c_level": None, "t_level": None}
    result = classify_event(event)
    assert result["c_level"] is None
    assert result["t_level"] is None


# ---------------------------------------------------------------------------
# _classify_ledger_row: nested cost_center handling
# ---------------------------------------------------------------------------


def test_classify_ledger_row_fills_nested_levels():
    """_classify_ledger_row lifts cost_center.model and fills c_level/t_level."""
    # Import the helper from reset_budget_daily_from_ledger
    mod = importlib.import_module("reset_budget_daily_from_ledger")
    row = {
        "decision_id": "abc123",
        "cost_center": {"model": "claude-opus-4-8", "c_level": None, "t_level": None},
        "confidence": "unknown",
    }
    result = mod._classify_ledger_row(row)
    assert result["cost_center"]["c_level"] == "C4"
    assert result["cost_center"]["t_level"] == "T4"
    assert result["confidence"] == "inferred"


def test_classify_ledger_row_preserves_existing_nested_levels():
    """Existing non-null levels in cost_center are not overwritten."""
    mod = importlib.import_module("reset_budget_daily_from_ledger")
    row = {
        "decision_id": "def456",
        "cost_center": {"model": "claude-opus-4-8", "c_level": "C1", "t_level": "T1"},
        "confidence": "router",
    }
    result = mod._classify_ledger_row(row)
    assert result["cost_center"]["c_level"] == "C1"
    assert result["cost_center"]["t_level"] == "T1"
    assert result["confidence"] == "router"


def test_classify_ledger_row_no_cost_center():
    """Row without cost_center returns unchanged."""
    mod = importlib.import_module("reset_budget_daily_from_ledger")
    row = {"decision_id": "ghi789", "confidence": "unknown"}
    result = mod._classify_ledger_row(row)
    assert result["decision_id"] == "ghi789"


def test_classify_ledger_row_empty_model():
    """Empty model in cost_center leaves levels as None."""
    mod = importlib.import_module("reset_budget_daily_from_ledger")
    row = {
        "decision_id": "jkl000",
        "cost_center": {"model": "", "c_level": None, "t_level": None},
        "confidence": "unknown",
    }
    result = mod._classify_ledger_row(row)
    # Should not have changed anything since model is empty
    assert result["cost_center"]["c_level"] is None
    assert result["cost_center"]["t_level"] is None
