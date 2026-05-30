"""Tests for the per-surface BASELINE audit."""

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "baseline_audit", _REPO / "scripts" / "baseline_audit.py"
)
ba = importlib.util.module_from_spec(_spec)
sys.modules["baseline_audit"] = ba
_spec.loader.exec_module(ba)  # type: ignore

_THRESH = {"mcp_tokens": {"warn": 3000, "max": 8000}}


class TestStatusFor:
    def test_ok_under_warn(self):
        assert ba.status_for(2000, _THRESH["mcp_tokens"]) == "ok"

    def test_warn_between(self):
        assert ba.status_for(5000, _THRESH["mcp_tokens"]) == "warn"

    def test_over_above_max(self):
        assert ba.status_for(9000, _THRESH["mcp_tokens"]) == "over"

    def test_unknown_when_none(self):
        assert ba.status_for(None, _THRESH["mcp_tokens"]) == "unknown"


class TestEvaluate:
    def test_overall_is_worst(self):
        m = {"mcp_tokens": 9000, "hook_count": 2}
        th = {
            "mcp_tokens": {"warn": 3000, "max": 8000},
            "hook_count": {"warn": 8, "max": 16},
        }
        r = ba.evaluate_baseline(m, th)
        assert r["overall"] == "over"
        assert r["metrics"]["mcp_tokens"]["status"] == "over"
        assert r["metrics"]["hook_count"]["status"] == "ok"

    def test_advice_only_on_warn_or_over(self):
        m = {"mcp_tokens": 2000}
        th = {"mcp_tokens": {"warn": 3000, "max": 8000}}
        r = ba.evaluate_baseline(m, th, {"mcp_tokens": "trim mcps"})
        assert r["metrics"]["mcp_tokens"]["advice"] == ""

    def test_advice_present_on_over(self):
        m = {"mcp_tokens": 9000}
        th = {"mcp_tokens": {"warn": 3000, "max": 8000}}
        r = ba.evaluate_baseline(m, th, {"mcp_tokens": "trim mcps"})
        assert r["metrics"]["mcp_tokens"]["advice"] == "trim mcps"

    def test_unknown_does_not_make_overall_over(self):
        r = ba.evaluate_baseline(
            {"mcp_tokens": None}, {"mcp_tokens": {"warn": 1, "max": 2}}
        )
        assert r["overall"] == "unknown"


class TestThresholds:
    def test_surface_override_wins(self):
        spec = {
            "defaults": {"mcp_tokens": {"warn": 8000, "max": 20000}},
            "surfaces": {"cli": {"mcp_tokens": {"warn": 3000, "max": 8000}}},
        }
        th = ba.thresholds_for(spec, "cli")
        assert th["mcp_tokens"]["max"] == 8000

    def test_defaults_when_no_surface(self):
        spec = {"defaults": {"hook_count": {"warn": 8, "max": 16}}, "surfaces": {}}
        th = ba.thresholds_for(spec, "cursor")
        assert th["hook_count"]["max"] == 16


class TestMeasurers:
    def test_mcp_tokens_from_manifest(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"mcp_tokens": 1447}), encoding="utf-8")
        assert ba.measure_mcp_tokens(p) == 1447.0

    def test_mcp_tokens_fallback_key(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(
            json.dumps({"mcp_audit": {"estimated_tokens_if_enabled": 5000}}),
            encoding="utf-8",
        )
        assert ba.measure_mcp_tokens(p) == 5000.0

    def test_mcp_tokens_unknown_when_absent(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text("{}", encoding="utf-8")
        assert ba.measure_mcp_tokens(p) is None

    def test_hook_count(self, tmp_path):
        s = tmp_path / "s.json"
        s.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [{"hooks": [{"a": 1}]}],
                        "PreToolUse": [{"hooks": [{"a": 1}, {"b": 2}]}],
                    }
                }
            ),
            encoding="utf-8",
        )
        assert ba.measure_hook_count(s) == 3.0

    def test_env_keys(self, tmp_path):
        s = tmp_path / "s.json"
        s.write_text(json.dumps({"env": {"A": "1", "B": "2"}}), encoding="utf-8")
        assert ba.measure_env_keys(s) == 2.0

    def test_manifest_age(self, tmp_path):
        from datetime import datetime, timezone

        p = tmp_path / "m.json"
        p.write_text(
            json.dumps({"generated_at": "2026-05-30T10:00:00+00:00"}), encoding="utf-8"
        )
        now = datetime(2026, 5, 30, 16, 0, 0, tzinfo=timezone.utc)
        assert ba.measure_manifest_age_hrs(p, now=now) == 6.0


def test_audit_surface_end_to_end():
    spec = {
        "defaults": {"mcp_tokens": {"warn": 8000, "max": 20000}},
        "surfaces": {"cli": {"mcp_tokens": {"warn": 3000, "max": 8000}}},
        "advice": {"mcp_tokens": "trim"},
    }
    card = ba.audit_surface("cli", spec=spec, measurements={"mcp_tokens": 9000})
    assert card["surface"] == "cli"
    assert card["overall"] == "over"
    assert card["metrics"]["mcp_tokens"]["advice"] == "trim"
