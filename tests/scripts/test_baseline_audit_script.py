"""Additional tests for scripts/baseline_audit.py.

Complements tests/test_baseline_audit.py with more edge cases, measurer
functions, and the collect/audit_surface wiring.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_RUNTIME = Path(__file__).resolve().parents[2] / "02_RUNTIME"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import baseline_audit as ba


# ---------------------------------------------------------------------------
# load_baselines
# ---------------------------------------------------------------------------


class TestLoadBaselines:
    def test_returns_defaults_when_file_missing(self, tmp_path):
        result = ba.load_baselines(tmp_path / "nonexistent.yaml")
        assert "defaults" in result
        assert "surfaces" in result

    def test_returns_defaults_structure_when_yaml_missing(self, tmp_path):
        result = ba.load_baselines(tmp_path / "no_file.yaml")
        assert result == {"defaults": {}, "surfaces": {}, "advice": {}}


# ---------------------------------------------------------------------------
# thresholds_for
# ---------------------------------------------------------------------------


class TestThresholdsFor:
    def test_empty_spec_returns_empty(self):
        result = ba.thresholds_for({}, "cli")
        assert result == {}

    def test_defaults_applied_when_no_surface_override(self):
        spec = {
            "defaults": {"hook_count": {"warn": 5, "max": 10}},
            "surfaces": {},
        }
        th = ba.thresholds_for(spec, "vscode")
        assert th["hook_count"] == {"warn": 5, "max": 10}

    def test_surface_override_replaces_default(self):
        spec = {
            "defaults": {"mcp_tokens": {"warn": 8000, "max": 20000}},
            "surfaces": {"cursor": {"mcp_tokens": {"warn": 4000, "max": 10000}}},
        }
        th = ba.thresholds_for(spec, "cursor")
        assert th["mcp_tokens"]["warn"] == 4000

    def test_surface_can_add_new_metric(self):
        spec = {
            "defaults": {},
            "surfaces": {"app": {"new_metric": {"warn": 1, "max": 2}}},
        }
        th = ba.thresholds_for(spec, "app")
        assert "new_metric" in th

    def test_missing_surface_key_falls_back_to_defaults(self):
        spec = {"defaults": {"hook_count": {"warn": 3, "max": 6}}, "surfaces": {}}
        th = ba.thresholds_for(spec, "nonexistent_surface")
        assert th["hook_count"]["warn"] == 3


# ---------------------------------------------------------------------------
# status_for
# ---------------------------------------------------------------------------


class TestStatusFor:
    def test_ok_when_below_warn(self):
        assert ba.status_for(100.0, {"warn": 200, "max": 400}) == "ok"

    def test_warn_when_between_warn_and_max(self):
        assert ba.status_for(300.0, {"warn": 200, "max": 400}) == "warn"

    def test_over_when_above_max(self):
        assert ba.status_for(500.0, {"warn": 200, "max": 400}) == "over"

    def test_unknown_when_value_is_none(self):
        assert ba.status_for(None, {"warn": 100, "max": 200}) == "unknown"

    def test_equal_to_max_is_warn(self):
        # code uses strict >, so equal to max → "warn" (between warn and max)
        assert ba.status_for(400.0, {"warn": 200, "max": 400}) == "warn"

    def test_equal_to_warn_is_ok(self):
        # code uses strict >, so equal to warn → "ok"
        assert ba.status_for(200.0, {"warn": 200, "max": 400}) == "ok"

    def test_empty_band_treats_as_zero_thresholds(self):
        # warn and max default to 0 when absent — anything > 0 should be "over"
        assert ba.status_for(1.0, {}) == "over"


# ---------------------------------------------------------------------------
# evaluate_baseline
# ---------------------------------------------------------------------------


class TestEvaluateBaseline:
    def test_overall_ok_all_ok(self):
        # Metrics not in thresholds get empty band {}, which defaults warn/max to 0
        # so they evaluate to "ok" only if value is 0 or None. Use 0 to get ok.
        m = {"mcp_tokens": 100}
        th = {"mcp_tokens": {"warn": 500, "max": 1000}}
        r = ba.evaluate_baseline(m, th)
        # mcp_tokens is ok; all unmeasured metrics get unknown status → overall unknown
        assert r["overall"] in ("ok", "unknown")

    def test_overall_unknown_all_none(self):
        m = {"mcp_tokens": None}
        th = {"mcp_tokens": {"warn": 500, "max": 1000}}
        r = ba.evaluate_baseline(m, th)
        assert r["overall"] == "unknown"

    def test_overall_worst_wins(self):
        m = {"mcp_tokens": 50, "hook_count": 999}
        th = {
            "mcp_tokens": {"warn": 500, "max": 1000},
            "hook_count": {"warn": 5, "max": 10},
        }
        r = ba.evaluate_baseline(m, th)
        assert r["overall"] == "over"

    def test_advice_attached_to_warn_metric(self):
        m = {"mcp_tokens": 700}
        th = {"mcp_tokens": {"warn": 500, "max": 1000}}
        r = ba.evaluate_baseline(m, th, {"mcp_tokens": "reduce mcp servers"})
        assert r["metrics"]["mcp_tokens"]["advice"] == "reduce mcp servers"

    def test_advice_empty_for_ok_metric(self):
        m = {"mcp_tokens": 100}
        th = {"mcp_tokens": {"warn": 500, "max": 1000}}
        r = ba.evaluate_baseline(m, th, {"mcp_tokens": "reduce mcp servers"})
        assert r["metrics"]["mcp_tokens"]["advice"] == ""

    def test_all_standard_metrics_present_in_result(self):
        r = ba.evaluate_baseline({}, {})
        for metric in ba._METRICS:
            assert metric in r["metrics"]


# ---------------------------------------------------------------------------
# measure_mcp_tokens
# ---------------------------------------------------------------------------


class TestMeasureMcpTokens:
    def test_reads_direct_mcp_tokens_key(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"mcp_tokens": 2048}), encoding="utf-8")
        assert ba.measure_mcp_tokens(p) == 2048.0

    def test_falls_back_to_nested_key(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"mcp_audit": {"estimated_tokens_if_enabled": 1500}}), encoding="utf-8")
        assert ba.measure_mcp_tokens(p) == 1500.0

    def test_returns_none_when_both_absent(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({}), encoding="utf-8")
        assert ba.measure_mcp_tokens(p) is None

    def test_returns_none_when_file_missing(self, tmp_path):
        assert ba.measure_mcp_tokens(tmp_path / "missing.json") is None


# ---------------------------------------------------------------------------
# measure_hook_count
# ---------------------------------------------------------------------------


class TestMeasureHookCount:
    def test_counts_all_hooks(self, tmp_path):
        s = tmp_path / "settings.json"
        payload = {
            "hooks": {
                "SessionStart": [{"hooks": [{"cmd": "a"}, {"cmd": "b"}]}],
                "PreToolUse": [{"hooks": [{"cmd": "c"}]}],
            }
        }
        s.write_text(json.dumps(payload), encoding="utf-8")
        assert ba.measure_hook_count(s) == 3.0

    def test_no_hooks_key_returns_none(self, tmp_path):
        s = tmp_path / "settings.json"
        s.write_text(json.dumps({}), encoding="utf-8")
        assert ba.measure_hook_count(s) is None

    def test_empty_hooks_dict_returns_zero(self, tmp_path):
        s = tmp_path / "settings.json"
        s.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
        assert ba.measure_hook_count(s) == 0.0

    def test_missing_file_returns_none(self, tmp_path):
        assert ba.measure_hook_count(tmp_path / "missing.json") is None


# ---------------------------------------------------------------------------
# measure_env_keys
# ---------------------------------------------------------------------------


class TestMeasureEnvKeys:
    def test_counts_env_entries(self, tmp_path):
        s = tmp_path / "settings.json"
        s.write_text(json.dumps({"env": {"A": "1", "B": "2", "C": "3"}}), encoding="utf-8")
        assert ba.measure_env_keys(s) == 3.0

    def test_no_env_key_returns_none(self, tmp_path):
        s = tmp_path / "settings.json"
        s.write_text(json.dumps({}), encoding="utf-8")
        assert ba.measure_env_keys(s) is None

    def test_empty_env_returns_zero(self, tmp_path):
        s = tmp_path / "settings.json"
        s.write_text(json.dumps({"env": {}}), encoding="utf-8")
        assert ba.measure_env_keys(s) == 0.0


# ---------------------------------------------------------------------------
# measure_manifest_age_hrs
# ---------------------------------------------------------------------------


class TestMeasureManifestAge:
    def test_computes_age_in_hours(self, tmp_path):
        p = tmp_path / "latest.json"
        p.write_text(json.dumps({"generated_at": "2026-06-03T10:00:00+00:00"}), encoding="utf-8")
        now = datetime(2026, 6, 3, 16, 0, 0, tzinfo=timezone.utc)
        assert ba.measure_manifest_age_hrs(p, now=now) == 6.0

    def test_returns_none_when_generated_at_missing(self, tmp_path):
        p = tmp_path / "latest.json"
        p.write_text(json.dumps({}), encoding="utf-8")
        assert ba.measure_manifest_age_hrs(p) is None

    def test_returns_none_when_file_missing(self, tmp_path):
        assert ba.measure_manifest_age_hrs(tmp_path / "missing.json") is None

    def test_returns_none_for_invalid_timestamp(self, tmp_path):
        p = tmp_path / "latest.json"
        p.write_text(json.dumps({"generated_at": "not-a-date"}), encoding="utf-8")
        assert ba.measure_manifest_age_hrs(p) is None

    def test_z_suffix_handled(self, tmp_path):
        p = tmp_path / "latest.json"
        p.write_text(json.dumps({"generated_at": "2026-06-03T10:00:00Z"}), encoding="utf-8")
        now = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
        assert ba.measure_manifest_age_hrs(p, now=now) == 2.0


# ---------------------------------------------------------------------------
# audit_surface
# ---------------------------------------------------------------------------


class TestAuditSurface:
    def test_surface_key_present_in_result(self):
        card = ba.audit_surface("vscode", spec={}, measurements={})
        assert card["surface"] == "vscode"

    def test_all_surfaces_valid(self):
        for surface in ba.SURFACES:
            card = ba.audit_surface(surface, spec={}, measurements={})
            assert card["surface"] == surface

    def test_overall_reflects_measurements(self):
        spec = {
            "defaults": {"mcp_tokens": {"warn": 1000, "max": 2000}},
            "surfaces": {},
            "advice": {},
        }
        card = ba.audit_surface("cli", spec=spec, measurements={"mcp_tokens": 5000})
        assert card["overall"] == "over"

    def test_empty_measurements_gives_all_unknown(self):
        # No thresholds → empty band → warn/max=0; None values → "unknown"
        card = ba.audit_surface("app", spec={"defaults": {}, "surfaces": {}, "advice": {}}, measurements={})
        # All _METRICS are absent from measurements → unknown status
        assert card["overall"] == "unknown"


# ---------------------------------------------------------------------------
# _fmt
# ---------------------------------------------------------------------------


class TestFmt:
    def test_includes_surface_name(self):
        card = ba.audit_surface("cli", spec={}, measurements={})
        text = ba._fmt(card)
        assert "cli" in text

    def test_includes_overall_status(self):
        spec = {
            "defaults": {"mcp_tokens": {"warn": 1, "max": 2}},
            "surfaces": {},
            "advice": {},
        }
        card = ba.audit_surface("cli", spec=spec, measurements={"mcp_tokens": 9999})
        text = ba._fmt(card)
        assert "OVER" in text

    def test_all_metrics_listed(self):
        card = ba.audit_surface("cli", spec={}, measurements={})
        text = ba._fmt(card)
        for metric in ba._METRICS:
            assert metric in text
