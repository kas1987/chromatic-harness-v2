"""Tests for gate.py: helper functions, blocking logic, advisory outputs.

The gate module is a PreToolUse hook that classifies Agent tool calls
and emits allow/deny decisions. Tests focus on the pure helper functions
and the mocked main() logic without touching stdin/stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure the router package is importable
_RUNTIME = Path(__file__).resolve().parents[4] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import router.gate as gate_mod
from router.pipeline.io import read_stdin, emit_advisory, emit_deny
from router.pipeline.impact import extract_file_refs, count_impacted, impact_fan_out
from router.pipeline.billing import billing_for_route, cost_estimate_usd
from router.pipeline.advisory import overlay_advisory, context_gate_advisory


# ── _has_tool_use ─────────────────────────────────────────────────────────────


class TestHasToolUse:
    def test_bash_detected(self):
        assert gate_mod._has_tool_use("run bash command") is True

    def test_glob_detected(self):
        assert gate_mod._has_tool_use("use glob to find files") is True

    def test_grep_detected(self):
        assert gate_mod._has_tool_use("grep for pattern") is True

    def test_npm_detected(self):
        assert gate_mod._has_tool_use("npm install packages") is True

    def test_pip_detected(self):
        assert gate_mod._has_tool_use("pip install requirements") is True

    def test_curl_detected(self):
        assert gate_mod._has_tool_use("curl the endpoint") is True

    def test_webfetch_detected(self):
        assert gate_mod._has_tool_use("webfetch the page") is True

    def test_execute_detected(self):
        assert gate_mod._has_tool_use("execute the script") is True

    def test_no_tool_use(self):
        assert gate_mod._has_tool_use("summarize this document") is False

    def test_empty_string(self):
        assert gate_mod._has_tool_use("") is False

    def test_case_insensitive(self):
        assert gate_mod._has_tool_use("BASH command") is True
        assert gate_mod._has_tool_use("GREP search") is True


# ── _overlay_advisory ─────────────────────────────────────────────────────────


class TestOverlayAdvisory:
    def test_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gate_mod, "_REPO", tmp_path)
        result = gate_mod._overlay_advisory()
        assert result == ""

    def test_returns_overlay_string(self, tmp_path, monkeypatch):
        overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
        overlay_dir.mkdir(parents=True)
        overlay_file = overlay_dir / "routing_policy_overlay.json"
        overlay_file.write_text(
            json.dumps({"c_to_t_threshold": 3, "allow_paid_spill": False}),
            encoding="utf-8",
        )
        monkeypatch.setattr(gate_mod, "_REPO", tmp_path)
        result = gate_mod._overlay_advisory()
        assert "overlay" in result
        assert "3" in result

    def test_returns_stale_fallback_string(self, tmp_path, monkeypatch):
        overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
        overlay_dir.mkdir(parents=True)
        overlay_file = overlay_dir / "routing_policy_overlay.json"
        overlay_file.write_text(
            json.dumps(
                {
                    "c_to_t_threshold": 2,
                    "allow_paid_spill": True,
                    "staleness_fallback": True,
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(gate_mod, "_REPO", tmp_path)
        result = gate_mod._overlay_advisory()
        assert "STALE-FALLBACK" in result

    def test_returns_empty_on_invalid_json(self, tmp_path, monkeypatch):
        overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
        overlay_dir.mkdir(parents=True)
        overlay_file = overlay_dir / "routing_policy_overlay.json"
        overlay_file.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr(gate_mod, "_REPO", tmp_path)
        result = gate_mod._overlay_advisory()
        assert result == ""


# ── read_stdin ────────────────────────────────────────────────────────────────


class TestReadStdin:
    def test_empty_stdin_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: ""))
        result = read_stdin()
        assert result == {}

    def test_valid_json_returns_dict(self, monkeypatch):
        payload = json.dumps({"tool_name": "Agent", "tool_input": {}})
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: payload))
        result = read_stdin()
        assert result["tool_name"] == "Agent"

    def test_invalid_json_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: "not json at all"))
        result = read_stdin()
        assert result == {}

    def test_non_dict_json_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: json.dumps([1, 2, 3])))
        result = read_stdin()
        assert result == {}


# ── emit_advisory and emit_deny ───────────────────────────────────────────────


class TestEmitAdvisory:
    def test_emit_advisory_writes_json(self, capsys):
        emit_advisory("ROUTER: test advisory")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "hookSpecificOutput" in data
        assert "test advisory" in data["hookSpecificOutput"]["additionalContext"]

    def test_emit_deny_writes_json_with_deny(self, capsys):
        emit_deny("ROUTER: too expensive")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "too expensive" in data["hookSpecificOutput"]["denyReason"]

    def test_emit_deny_includes_advisory_context(self, capsys):
        emit_deny("ROUTER: block reason")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "block reason" in data["hookSpecificOutput"]["additionalContext"]


# ── extract_file_refs and count_impacted ─────────────────────────────────────


class TestExtractFileRefs:
    def test_no_file_refs_returns_empty(self):
        result = extract_file_refs("no file references here")
        assert result == []

    def test_count_impacted_empty_returns_zero(self):
        assert count_impacted("") == 0
        assert count_impacted(None) == 0  # type: ignore[arg-type]

    def test_count_impacted_counts_paths(self):
        stdout = "src/foo.py\nsrc/bar.py\ntest/test_foo.py\n"
        assert count_impacted(stdout) == 3

    def test_count_impacted_deduplicates(self):
        stdout = "src/foo.py\nsrc/foo.py\nsrc/bar.py\n"
        assert count_impacted(stdout) == 2

    def test_count_impacted_ignores_blank_lines(self):
        stdout = "src/foo.py\n\n\nsrc/bar.py\n"
        assert count_impacted(stdout) == 2


# ── impact_fan_out ────────────────────────────────────────────────────────────


class TestImpactFanOut:
    def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setattr("router.pipeline.impact.IMPACT_ENABLED", False)
        result = impact_fan_out("any description", "any prompt")
        assert result is None

    def test_returns_none_when_no_file_refs(self, monkeypatch):
        monkeypatch.setattr("router.pipeline.impact.IMPACT_ENABLED", True)
        # No file references in description/prompt → should return None
        result = impact_fan_out("abstract task with no files", "")
        assert result is None


# ── cost_estimate_usd ─────────────────────────────────────────────────────────


class TestCostEstimateUsd:
    def test_zero_tokens_returns_zero(self):
        result = cost_estimate_usd("mock", 0)
        assert result == 0.0

    def test_free_provider_returns_zero(self):
        # local providers like ollama have zero cost
        result = cost_estimate_usd("ollama", 10000)
        assert result == 0.0

    def test_returns_float(self):
        result = cost_estimate_usd("openai", 1000)
        assert isinstance(result, float)

    def test_returns_non_negative(self):
        result = cost_estimate_usd("openai", 50000)
        assert result >= 0.0

    def test_higher_tokens_costs_more(self):
        low = cost_estimate_usd("openai", 1000)
        high = cost_estimate_usd("openai", 100000)
        # Should cost more with more tokens (if provider has a cost)
        assert high >= low


# ── billing_for_route ─────────────────────────────────────────────────────────


class TestBillingForRoute:
    def test_returns_dict_with_required_keys(self):
        result = billing_for_route("mock")
        assert "cost_estimate_usd" in result
        assert "billing_axis" in result
        assert "billing_tokens" in result
        assert "budget_gate_estimate_usd" in result

    def test_cost_is_float(self):
        result = billing_for_route("mock")
        assert isinstance(result["cost_estimate_usd"], float)

    def test_local_provider_cost_is_zero(self):
        result = billing_for_route("native_claude")
        # Axis P is free
        assert result["cost_estimate_usd"] == 0.0


# ── main() gate logic (blocked via shouldBlock) ──────────────────────────────


class TestMainGateLogic:
    """Test the blocking decision logic extracted from main()."""

    def test_non_agent_tool_passes_through(self, monkeypatch, capsys):
        """Non-Agent tools should always get an advisory (not a block)."""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: payload))

        with patch("router.gate.log_entry"), patch("router.gate.audit_router_decision"):
            with pytest.raises(SystemExit) as exc_info:
                gate_mod.main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "ROUTER: non-Agent tool" in data["hookSpecificOutput"]["additionalContext"]

    def test_haiku_model_cap_blocks(self, monkeypatch, capsys):
        """Caller requesting haiku but classifier returning tier>1 should block."""
        payload = json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {
                    "description": "write unit tests",
                    "prompt": "",
                    "subagent_type": "general-purpose",
                    "model": "haiku",
                },
            }
        )
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: payload))

        with patch("router.gate.log_entry"), patch("router.gate.audit_router_decision"):
            with pytest.raises(SystemExit) as exc_info:
                gate_mod.main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # haiku at tier > 1 should be blocked
        assert data["hookSpecificOutput"].get("permissionDecision") == "deny"

    def test_opus_model_always_allowed(self, monkeypatch, capsys):
        """Caller requesting opus should always be allowed (native_claude, tier 4)."""
        payload = json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {
                    "description": "complex architecture task",
                    "prompt": "",
                    "subagent_type": "general-purpose",
                    "model": "opus",
                },
            }
        )
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: payload))

        with patch("router.gate.log_entry"), patch("router.gate.audit_router_decision"):
            with pytest.raises(SystemExit) as exc_info:
                gate_mod.main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # opus should NOT be denied
        assert data["hookSpecificOutput"].get("permissionDecision") != "deny"
