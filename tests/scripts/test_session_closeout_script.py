"""Unit tests for scripts/session_closeout.py.

Covers: helper functions that don't require heavy subprocess/DB integration —
_coerce_float, _coerce_int, _extract_issue_id, _parse_utc,
_load_issue_rows_jsonl, _load_governance_signals, _coverage_as_float,
promote_learnings_to_wiki, _default_epic_swot_policy_config,
_sanitize_epic_swot_policy_config, _load_auto_turn_policy_config,
find_latest_open_swot_epic (jsonl path), _post_mortem_stamp,
_select_auto_turn_artifact_kind, and evaluate_ship_completion (no magnet).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO = Path(__file__).resolve().parents[2]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

_spec = importlib.util.spec_from_file_location("session_closeout", _REPO / "scripts" / "session_closeout.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# _coerce_float
# ---------------------------------------------------------------------------


def test_coerce_float_valid():
    assert sc._coerce_float("0.75", 0.5) == 0.75


def test_coerce_float_returns_default_for_str():
    assert sc._coerce_float("nope", 0.5) == 0.5


def test_coerce_float_returns_default_below_minimum():
    assert sc._coerce_float(-0.1, 0.5, minimum=0.0) == 0.5


def test_coerce_float_returns_default_above_maximum():
    assert sc._coerce_float(1.5, 0.5, maximum=1.0) == 0.5


def test_coerce_float_allows_none_maximum():
    assert sc._coerce_float(999.0, 0.5, maximum=None) == 999.0


# ---------------------------------------------------------------------------
# _coerce_int
# ---------------------------------------------------------------------------


def test_coerce_int_valid():
    assert sc._coerce_int("7", 0) == 7


def test_coerce_int_returns_default_for_non_numeric():
    assert sc._coerce_int("abc", 3) == 3


def test_coerce_int_returns_default_below_minimum():
    assert sc._coerce_int(-1, 5, minimum=0) == 5


def test_coerce_int_accepts_zero_minimum():
    assert sc._coerce_int(0, 1, minimum=0) == 0


# ---------------------------------------------------------------------------
# _extract_issue_id
# ---------------------------------------------------------------------------


def test_extract_issue_id_from_created_line():
    assert sc._extract_issue_id("Created issue: abc-123") == "abc-123"


def test_extract_issue_id_from_bare_id():
    result = sc._extract_issue_id("Some text chromatic-harness-v2-42 done")
    assert result == "chromatic-harness-v2-42"


def test_extract_issue_id_empty_string():
    assert sc._extract_issue_id("") == ""


def test_extract_issue_id_no_match():
    assert sc._extract_issue_id("no id here at all") == ""


# ---------------------------------------------------------------------------
# _parse_utc
# ---------------------------------------------------------------------------


def test_parse_utc_z_suffix():
    dt = sc._parse_utc("2026-06-01T12:00:00Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2026


def test_parse_utc_iso_format():
    dt = sc._parse_utc("2026-06-01T12:00:00+00:00")
    assert dt is not None
    assert dt.tzinfo == timezone.utc


def test_parse_utc_empty_string():
    assert sc._parse_utc("") is None


def test_parse_utc_invalid_string():
    assert sc._parse_utc("not-a-date") is None


# ---------------------------------------------------------------------------
# _load_issue_rows_jsonl
# ---------------------------------------------------------------------------


def test_load_issue_rows_jsonl_parses_valid_lines(tmp_path):
    f = tmp_path / "issues.jsonl"
    f.write_text('{"id":"a1","title":"T1"}\n{"id":"a2","title":"T2"}\n', encoding="utf-8")
    rows = sc._load_issue_rows_jsonl(f)
    assert len(rows) == 2
    assert rows[0]["id"] == "a1"


def test_load_issue_rows_jsonl_skips_blank_lines(tmp_path):
    f = tmp_path / "issues.jsonl"
    f.write_text('\n{"id":"b1"}\n\n', encoding="utf-8")
    rows = sc._load_issue_rows_jsonl(f)
    assert len(rows) == 1


def test_load_issue_rows_jsonl_skips_malformed(tmp_path):
    f = tmp_path / "issues.jsonl"
    f.write_text('{"id":"c1"}\nNOT JSON\n', encoding="utf-8")
    rows = sc._load_issue_rows_jsonl(f)
    assert len(rows) == 1


def test_load_issue_rows_jsonl_missing_file(tmp_path):
    rows = sc._load_issue_rows_jsonl(tmp_path / "absent.jsonl")
    assert rows == []


# ---------------------------------------------------------------------------
# _load_governance_signals
# ---------------------------------------------------------------------------


def test_load_governance_signals_valid(tmp_path):
    f = tmp_path / "gov.json"
    f.write_text(json.dumps({"event_count": 42, "canonical_coverage": {"provider": 0.9}}), encoding="utf-8")
    sig = sc._load_governance_signals(f)
    assert sig["event_count"] == 42
    assert sig["canonical_coverage"]["provider"] == 0.9


def test_load_governance_signals_missing_file(tmp_path):
    sig = sc._load_governance_signals(tmp_path / "absent.json")
    assert sig["event_count"] == 0


def test_load_governance_signals_invalid_json(tmp_path):
    f = tmp_path / "gov.json"
    f.write_text("NOT JSON", encoding="utf-8")
    sig = sc._load_governance_signals(f)
    assert sig["event_count"] == 0


# ---------------------------------------------------------------------------
# _coverage_as_float
# ---------------------------------------------------------------------------


def test_coverage_as_float_numeric():
    assert sc._coverage_as_float(0.9) == 0.9


def test_coverage_as_float_dict_coverage_key():
    assert sc._coverage_as_float({"coverage": 0.8}) == 0.8


def test_coverage_as_float_dict_value_key():
    assert sc._coverage_as_float({"value": 0.7}) == 0.7


def test_coverage_as_float_empty_dict():
    assert sc._coverage_as_float({}) == 0.0


def test_coverage_as_float_non_numeric():
    assert sc._coverage_as_float("bad") == 0.0


# ---------------------------------------------------------------------------
# promote_learnings_to_wiki
# ---------------------------------------------------------------------------


def test_promote_learnings_to_wiki_happy_path():
    def fake_run(cmd):
        return 0, json.dumps({"promoted": 3})

    result = sc.promote_learnings_to_wiki(execute=True, runner=fake_run)
    assert result["ok"] is True
    assert result["promoted"] == 3


def test_promote_learnings_to_wiki_nonzero_exit():
    def fake_run(cmd):
        return 1, ""

    result = sc.promote_learnings_to_wiki(execute=True, runner=fake_run)
    assert result["ok"] is False
    assert "exited 1" in result["skipped_reason"]


def test_promote_learnings_to_wiki_malformed_json():
    def fake_run(cmd):
        return 0, "NOT JSON"

    result = sc.promote_learnings_to_wiki(execute=True, runner=fake_run)
    assert result["ok"] is False
    assert "malformed JSON" in result["skipped_reason"]


def test_promote_learnings_to_wiki_dry_run_flag():
    recorded = {}

    def fake_run(cmd):
        recorded["cmd"] = cmd
        return 0, json.dumps({"promoted": 0})

    sc.promote_learnings_to_wiki(execute=False, runner=fake_run)
    assert "--dry-run" in recorded["cmd"]


# ---------------------------------------------------------------------------
# _default_epic_swot_policy_config & _sanitize_epic_swot_policy_config
# ---------------------------------------------------------------------------


def test_default_epic_swot_policy_config_has_required_keys():
    cfg = sc._default_epic_swot_policy_config()
    for key in ("confidence_threshold", "block_penalty", "history_windows", "history_limits", "session_tokens"):
        assert key in cfg


def test_sanitize_epic_swot_policy_preserves_valid_override():
    defaults = sc._default_epic_swot_policy_config()
    overrides = dict(defaults)
    overrides["confidence_threshold"] = 0.7
    sanitized = sc._sanitize_epic_swot_policy_config(overrides, defaults)
    assert sanitized["confidence_threshold"] == 0.7


def test_sanitize_epic_swot_policy_rejects_out_of_range():
    defaults = sc._default_epic_swot_policy_config()
    bad = dict(defaults)
    bad["confidence_threshold"] = 5.0  # > 1.0 — must fall back to default
    sanitized = sc._sanitize_epic_swot_policy_config(bad, defaults)
    assert sanitized["confidence_threshold"] == defaults["confidence_threshold"]


# ---------------------------------------------------------------------------
# _load_auto_turn_policy_config
# ---------------------------------------------------------------------------


def test_load_auto_turn_policy_config_defaults_when_missing(tmp_path):
    cfg = sc._load_auto_turn_policy_config(tmp_path / "absent.json")
    assert "required_signal_hits" in cfg
    assert "signals" in cfg


def test_load_auto_turn_policy_config_reads_valid_file(tmp_path):
    f = tmp_path / "policy.json"
    f.write_text(json.dumps({"required_signal_hits": 3}), encoding="utf-8")
    cfg = sc._load_auto_turn_policy_config(f)
    assert cfg["required_signal_hits"] == 3


def test_load_auto_turn_policy_config_ignores_invalid_json(tmp_path):
    f = tmp_path / "policy.json"
    f.write_text("NOT JSON", encoding="utf-8")
    cfg = sc._load_auto_turn_policy_config(f)
    # Should return defaults
    assert "required_signal_hits" in cfg


# ---------------------------------------------------------------------------
# find_latest_open_swot_epic (JSONL path)
# ---------------------------------------------------------------------------


def test_find_latest_open_swot_epic_from_jsonl(tmp_path, monkeypatch):
    issues = tmp_path / "issues.jsonl"
    rows = [
        {
            "id": "epic-001",
            "title": "EPIC-SWOT NEXT [20260601T120000Z]",
            "status": "open",
            "issue_type": "epic",
            "created_at": "2026-06-01T12:00:00Z",
        }
    ]
    issues.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    # Force live query to fail so JSONL fallback is used
    monkeypatch.setattr(sc, "_fetch_swot_rows_live", lambda: None)
    result = sc.find_latest_open_swot_epic(issues_path=issues)
    assert result.get("epic_id") == "epic-001"


def test_find_latest_open_swot_epic_returns_empty_when_no_epics(tmp_path, monkeypatch):
    issues = tmp_path / "issues.jsonl"
    issues.write_text(
        '{"id":"t1","title":"plain task","status":"open","issue_type":"task","created_at":"2026-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sc, "_fetch_swot_rows_live", lambda: None)
    result = sc.find_latest_open_swot_epic(issues_path=issues)
    assert result == {}


# ---------------------------------------------------------------------------
# _post_mortem_stamp
# ---------------------------------------------------------------------------


def test_post_mortem_stamp_returns_date_and_ts():
    date_part, ts_part = sc._post_mortem_stamp()
    assert len(date_part) == 10 and "-" in date_part  # YYYY-MM-DD
    assert "T" in ts_part and ts_part.endswith("Z")


def test_post_mortem_stamp_uses_provided_datetime():
    fixed = datetime(2026, 6, 3, 14, 30, 0, tzinfo=timezone.utc)
    date_part, ts_part = sc._post_mortem_stamp(fixed)
    assert date_part == "2026-06-03"
    assert ts_part == "20260603T143000Z"


# ---------------------------------------------------------------------------
# _select_auto_turn_artifact_kind
# ---------------------------------------------------------------------------


def test_select_auto_turn_artifact_kind_checkpoint_when_beads():
    assert sc._select_auto_turn_artifact_kind({"beads_ready": ["b1", "b2"]}) == "checkpoint"


def test_select_auto_turn_artifact_kind_post_mortem_when_no_beads():
    assert sc._select_auto_turn_artifact_kind({"beads_ready": []}) == "post_mortem"


def test_select_auto_turn_artifact_kind_post_mortem_when_key_absent():
    assert sc._select_auto_turn_artifact_kind({}) == "post_mortem"


# ---------------------------------------------------------------------------
# evaluate_ship_completion
# ---------------------------------------------------------------------------


def test_evaluate_ship_completion_no_evidence_skips(tmp_path):
    result = sc.evaluate_ship_completion(["B1"], evidence_path=tmp_path / "absent.json")
    assert result["ok"] is True
    assert result["block_close"] == []
    assert result["applicable"] is False


def test_evaluate_ship_completion_malformed_evidence(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text("{not json}", encoding="utf-8")
    result = sc.evaluate_ship_completion(["B1"], evidence_path=p)
    assert result["ok"] is False


def test_evaluate_ship_completion_empty_dict_evidence(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text("{}", encoding="utf-8")
    result = sc.evaluate_ship_completion(["B1"], evidence_path=p)
    # Empty dict → skip_reason set
    assert "skip_reason" in result
