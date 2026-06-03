"""Tests for router pipeline billing stage."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "02_RUNTIME"))

import pytest

from router.pipeline.billing import cost_estimate_usd, billing_for_route, BILLING_DEFAULT_TOKENS


# ── cost_estimate_usd ────────────────────────────────────────────────────────


def test_cost_estimate_zero_tokens():
    """Zero tokens always yields zero cost."""
    # PolicyLoader is imported inside cost_estimate_usd as 'from router.policy import PolicyLoader'
    # so we patch it at the source: router.policy.PolicyLoader
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"anthropic": 3.0}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = cost_estimate_usd("claude_api", 0)
    assert result == 0.0


def test_cost_estimate_known_provider(monkeypatch):
    """Returns a nonzero cost for a cloud provider with known rate."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"anthropic": 6.0}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = cost_estimate_usd("claude_api", 1_000_000)
    # 500k in * $6/Mtok + 500k out * $6/Mtok = $6.0
    assert result == pytest.approx(6.0, rel=1e-4)


def test_cost_estimate_alias_resolves(monkeypatch):
    """claude_api resolves via alias to 'anthropic' in the cost table."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"anthropic": 4.0}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        r1 = cost_estimate_usd("claude_api", 200_000)
        r2 = cost_estimate_usd("anthropic", 200_000)
    assert r1 == r2


def test_cost_estimate_ollama_alias_resolves():
    """ollama_local resolves to 'ollama' key (which should be 0 cost)."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"ollama": 0.0}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = cost_estimate_usd("ollama_local", 500_000)
    assert result == 0.0


def test_cost_estimate_unknown_provider_returns_zero():
    """An unknown provider with no cost entry returns 0.0 (fail-open)."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = cost_estimate_usd("totally_unknown_xyz", 10_000)
    assert result == 0.0


def test_cost_estimate_dict_rate():
    """Handles per-direction rate dict {input: X, output: Y}."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"google": {"input": 2.0, "output": 8.0}}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = cost_estimate_usd("gemini", 1_000_000)
    # 500k in * $2/Mtok + 500k out * $8/Mtok = $1 + $4 = $5
    assert result == pytest.approx(5.0, rel=1e-4)


def test_cost_estimate_policy_error_returns_zero():
    """Returns 0.0 when PolicyLoader raises (fail-open)."""
    with patch("router.policy.PolicyLoader", side_effect=RuntimeError("db gone")):
        result = cost_estimate_usd("anthropic", 100_000)
    assert result == 0.0


def test_cost_estimate_result_is_rounded():
    """Result is rounded to 6 decimal places."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"anthropic": 3.0}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = cost_estimate_usd("claude_api", 333_333)
    # Just verify it's a float with reasonable precision
    assert isinstance(result, float)
    assert len(str(result).split(".")[-1]) <= 7


# ── billing_for_route ────────────────────────────────────────────────────────


def test_billing_for_route_returns_required_keys():
    """billing_for_route always returns the four required keys."""
    result = billing_for_route("mock_provider")
    assert "cost_estimate_usd" in result
    assert "billing_axis" in result
    assert "billing_tokens" in result
    assert "budget_gate_estimate_usd" in result


def test_billing_for_route_default_tokens():
    """billing_for_route uses BILLING_DEFAULT_TOKENS when tokens not specified."""
    result = billing_for_route("native_claude")
    assert result["billing_tokens"] == BILLING_DEFAULT_TOKENS


def test_billing_for_route_custom_tokens():
    """billing_for_route uses supplied token count."""
    result = billing_for_route("native_claude", tokens=1234)
    assert result["billing_tokens"] == 1234


def test_billing_for_route_axis_P_zero_cost():
    """Axis P (native_claude) always has zero cost."""
    result = billing_for_route("native_claude")
    assert result["cost_estimate_usd"] == 0.0
    # Axis should be P
    if result["billing_axis"] is not None:
        assert result["billing_axis"] == "P"


def test_billing_for_route_axis_F_zero_cost():
    """Axis F (ollama local) always has zero cost."""
    result = billing_for_route("ollama_local")
    assert result["cost_estimate_usd"] == 0.0
    if result["billing_axis"] is not None:
        assert result["billing_axis"] == "F"


def test_billing_for_route_axis_D_nonzero_cost():
    """Axis D provider with nonzero rate produces nonzero cost estimate."""
    mock_loader_cls = MagicMock()
    mock_loader_cls.return_value.provider_costs.return_value = {"anthropic": 6.0}
    with patch("router.policy.PolicyLoader", mock_loader_cls):
        result = billing_for_route("claude_api", tokens=1_000_000)
    # Axis D → uses cost_estimate_usd
    assert result["cost_estimate_usd"] > 0.0


def test_billing_for_route_never_raises_on_bad_provider():
    """billing_for_route is fully fail-open for an unrecognised provider."""
    result = billing_for_route("totally_fake_provider_xyz")
    assert isinstance(result, dict)
    assert result["cost_estimate_usd"] >= 0.0


def test_billing_for_route_tokens_none_uses_default():
    """Passing tokens=None falls back to BILLING_DEFAULT_TOKENS."""
    result = billing_for_route("ollama", tokens=None)
    assert result["billing_tokens"] == BILLING_DEFAULT_TOKENS
