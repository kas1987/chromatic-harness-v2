"""Unit tests for router/pipeline/* middleware stages.

Each stage is tested independently of gate.py to verify the 'reusable outside
the hook context' requirement (bead chromatic-harness-v2-u8uj.2).
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# ── io stage ────────────────────────────────────────────────────────────────


def test_read_stdin_valid_json():
    from router.pipeline.io import read_stdin

    with patch("sys.stdin", StringIO('{"tool_name": "Agent"}')):
        assert read_stdin() == {"tool_name": "Agent"}


def test_read_stdin_empty_returns_empty_dict():
    from router.pipeline.io import read_stdin

    with patch("sys.stdin", StringIO("")):
        assert read_stdin() == {}


def test_read_stdin_invalid_json_returns_empty_dict():
    from router.pipeline.io import read_stdin

    with patch("sys.stdin", StringIO("not json {")):
        assert read_stdin() == {}


def test_emit_advisory_writes_hookspecificoutput(capsys):
    from router.pipeline.io import emit_advisory

    with patch.object(sys.stdout, "reconfigure"):
        emit_advisory("hello")

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["additionalContext"] == "hello"


def test_emit_deny_sets_permission_decision(capsys):
    from router.pipeline.io import emit_deny

    with patch.object(sys.stdout, "reconfigure"):
        emit_deny("too expensive")

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "too expensive" in payload["hookSpecificOutput"]["denyReason"]


# ── impact stage ─────────────────────────────────────────────────────────────


def test_extract_file_refs_deduped():
    from router.pipeline.impact import extract_file_refs

    text = "02_RUNTIME/router/gate.py and 02_RUNTIME/router/gate.py again"
    refs = extract_file_refs(text)
    assert refs.count("02_RUNTIME/router/gate.py") == 1


def test_count_impacted_excludes_blank_and_no_sep():
    from router.pipeline.impact import count_impacted

    assert count_impacted("a/b.py\na/b.py\nnotapath\n\n") == 1


def test_impact_fan_out_disabled(monkeypatch):
    import router.pipeline.impact as m

    monkeypatch.setattr(m, "IMPACT_ENABLED", False)
    from router.pipeline.impact import impact_fan_out

    assert impact_fan_out("edit 02_RUNTIME/router/gate.py", "") is None


# ── billing stage ────────────────────────────────────────────────────────────


def test_billing_for_route_returns_required_keys():
    from router.pipeline.billing import billing_for_route

    result = billing_for_route("native_claude")
    assert "cost_estimate_usd" in result
    assert "billing_axis" in result
    assert "billing_tokens" in result
    assert "budget_gate_estimate_usd" in result


def test_billing_for_route_tokens_override():
    from router.pipeline.billing import billing_for_route

    result = billing_for_route("native_claude", tokens=1000)
    assert result["billing_tokens"] == 1000


def test_cost_estimate_usd_failopen_unknown_provider():
    from router.pipeline.billing import cost_estimate_usd

    # Unknown provider → 0.0, never raises.
    assert cost_estimate_usd("nonexistent_provider_xyz", 10000) == 0.0


# ── advisory stage ───────────────────────────────────────────────────────────


def test_read_routing_overlay_missing_file_returns_none(tmp_path, monkeypatch):
    import router.pipeline.advisory as adv

    monkeypatch.setattr(adv, "_REPO", tmp_path)
    adv._REPO = tmp_path  # reset lazy cache
    from router.pipeline.advisory import read_routing_overlay

    assert read_routing_overlay() is None


def test_read_routing_overlay_reads_valid_json(tmp_path):
    import router.pipeline.advisory as adv

    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text(
        json.dumps({"c_to_t_threshold": 3, "allow_paid_spill": False})
    )
    adv._REPO = tmp_path
    from router.pipeline.advisory import read_routing_overlay

    result = read_routing_overlay()
    assert result is not None
    assert result["c_to_t_threshold"] == 3
    adv._REPO = None  # reset


def test_overlay_advisory_empty_when_no_overlay(tmp_path, monkeypatch):
    import router.pipeline.advisory as adv

    adv._REPO = tmp_path
    from router.pipeline.advisory import overlay_advisory

    assert overlay_advisory() == ""
    adv._REPO = None


# ── audit stage ──────────────────────────────────────────────────────────────


def test_log_entry_appends_to_file(tmp_path, monkeypatch):
    import router.pipeline.audit as aud

    monkeypatch.setattr(aud, "LOG_DIR", tmp_path)
    monkeypatch.setattr(aud, "LOG_FILE", tmp_path / "log.jsonl")
    from router.pipeline.audit import log_entry

    log_entry({"event": "test", "value": 42})
    lines = (tmp_path / "log.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "test"


def test_log_entry_rotates_when_over_limit(tmp_path, monkeypatch):
    import router.pipeline.audit as aud

    monkeypatch.setattr(aud, "LOG_DIR", tmp_path)
    log_file = tmp_path / "log.jsonl"
    monkeypatch.setattr(aud, "LOG_FILE", log_file)
    monkeypatch.setattr(aud, "MAX_LOG_LINES", 5)
    from router.pipeline.audit import log_entry

    for i in range(6):
        log_entry({"i": i})

    lines = log_file.read_text().splitlines()
    assert len(lines) == 4  # 80% of 5 = 4
