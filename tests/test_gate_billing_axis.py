"""gate.py route-log billing backfill (bead B4 — TOKEN_ECONOMY_SPEC.md §2/§3/§5).

Asserts the daily routing log (routes_*.jsonl) now carries a non-null
``cost_estimate_usd`` and a 3-axis ``billing_axis`` (P/D/F), plus the canonical
``decision_id`` join key, and that the BudgetGate.estimate advisory is wired
fail-open. None of this changes routing decisions.

Run with: pytest tests/test_gate_billing_axis.py -v
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone

import router.gate as gate

importlib.reload(gate)


def test_billing_for_route_dollar_axis_nonnull_cost():
    # anthropic is a frontier (Axis D) provider with non-zero $ rates.
    out = gate._billing_for_route("anthropic", tokens=1_000_000)
    assert out["billing_axis"] == "D"
    assert out["cost_estimate_usd"] is not None
    assert out["cost_estimate_usd"] > 0.0
    # Advisory BudgetGate.estimate must be wired (fail-open → may be 0.0/float).
    assert isinstance(out["budget_gate_estimate_usd"], float)


def test_billing_for_route_prepaid_axis_zero_marginal():
    out = gate._billing_for_route("native_claude", tokens=500_000)
    assert out["billing_axis"] == "P"  # prepaid quota, not dollar-billed
    assert out["cost_estimate_usd"] == 0.0  # $0 marginal in-session


def test_billing_for_route_local_axis_free():
    out = gate._billing_for_route("ollama_remote_desktop", tokens=500_000)
    assert out["billing_axis"] == "F"
    assert out["cost_estimate_usd"] == 0.0


def test_cost_estimate_failopen_unknown_provider():
    # Unknown provider → no exception, 0.0 cost.
    assert gate._cost_estimate_usd("does_not_exist", 1000) == 0.0


def test_route_log_carries_nonnull_cost_and_axis():
    """End-to-end: _audit_router_decision writes a route log line with the
    backfilled fields and the decision_id join key."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": "billing-axis e2e probe",
        "subagent_type": "general-purpose",
        "provider": "anthropic",
        "target_model": "claude-3",
        "tier": 3,
        "reason": "test",
        "blocked": False,
        "c_level": "C3",
        "speed_mode": "balance",
        "c_confidence": 0.9,
    }
    gate._audit_router_decision(entry)

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    log = gate._REPO / "07_LOGS_AND_AUDIT" / "routing" / f"routes_{today}.jsonl"
    assert log.is_file()
    rows = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln]
    mine = [r for r in rows if r.get("task_id", "").startswith("billing-axis e2e")]
    assert mine, "route-log line was not written"
    row = mine[-1]
    assert row["cost_estimate_usd"] is not None
    assert row["cost_estimate_usd"] > 0.0
    assert row["billing_axis"] == "D"
    assert row.get("decision_id")  # non-empty join key for B3
