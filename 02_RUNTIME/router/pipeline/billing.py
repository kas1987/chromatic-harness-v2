"""Billing stage: estimate USD cost and 3-axis billing label for a route.

Always fail-open — telemetry must never block or alter a routing decision.
"""

from __future__ import annotations

import os
from typing import Any

# Default token assumption when the hook has no per-request max_tokens.
_CONTEXT_MAX_TOKENS = int(os.environ.get("ROUTER_CONTEXT_MAX_TOKENS", "128000"))
BILLING_DEFAULT_TOKENS = int(os.environ.get("ROUTER_BILLING_DEFAULT_TOKENS", str(_CONTEXT_MAX_TOKENS // 2)))

# Map selector provider IDs → budget-policy.yaml cost-estimate keys.
_COST_KEY_ALIASES: dict[str, str] = {
    "claude_api": "anthropic",
    "ollama_local": "ollama",
    "ollama_remote_desktop": "ollama",
    "gemini": "google",
    "together": "openrouter",
    "together_ai": "openrouter",
}


def cost_estimate_usd(provider: str, tokens: int) -> float:
    """Estimate marginal USD for provider over tokens (fail-open → 0.0).

    Tokens split 50/50 across input/output rates as a flat estimate.
    Axis P (native_claude) and Axis F (local) resolve to 0.0 by their rates.
    """
    try:
        from router.policy import PolicyLoader

        costs = PolicyLoader().provider_costs() or {}
        key = _COST_KEY_ALIASES.get(provider, provider)
        rate = costs.get(key, costs.get(provider, 0.0))
        if isinstance(rate, dict):
            in_rate = float(rate.get("input", 0.0))
            out_rate = float(rate.get("output", 0.0))
        else:
            in_rate = out_rate = float(rate or 0.0)
        half = tokens / 2.0
        usd = (half / 1_000_000.0) * in_rate + (half / 1_000_000.0) * out_rate
        return round(usd, 6)
    except Exception:  # noqa: BLE001
        return 0.0


def billing_for_route(provider: str, tokens: int | None = None) -> dict[str, Any]:
    """Compute {cost_estimate_usd, billing_axis} for the route log (fail-open).

    BudgetGate.estimate is advisory-only (spec §7) — recorded but never used
    to block or change the routing decision.
    """
    import importlib
    import importlib.util
    from pathlib import Path

    tok = int(tokens if tokens is not None else BILLING_DEFAULT_TOKENS)
    out: dict[str, Any] = {
        "cost_estimate_usd": 0.0,
        "billing_axis": None,
        "billing_tokens": tok,
        "budget_gate_estimate_usd": None,
    }

    # Load billing_axis via importlib so this module works standalone.
    try:
        _ba_path = Path(__file__).resolve().parents[1] / "billing_axis.py"
        spec = importlib.util.spec_from_file_location("router.billing_axis", _ba_path)
        _ba = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(_ba)  # type: ignore[union-attr]
        out["billing_axis"] = _ba.classify(provider)
    except Exception:  # noqa: BLE001
        pass

    if out["billing_axis"] in ("P", "F"):
        out["cost_estimate_usd"] = 0.0
    else:
        out["cost_estimate_usd"] = cost_estimate_usd(provider, tok)

    try:
        from router.budget import BudgetGate

        out["budget_gate_estimate_usd"] = BudgetGate().estimate(provider, tok)
    except Exception:  # noqa: BLE001
        pass

    return out
