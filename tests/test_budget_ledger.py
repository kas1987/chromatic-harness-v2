"""Tests for agent budget ledger and transfer decisions."""

from __future__ import annotations

import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"

if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget.ledger import (  # noqa: E402
    BudgetLedger,
    BudgetSnapshot,
    decide_transfer,
    daily_cap_usd,
    load_agent_budget_config,
)


def test_load_agent_budget_config():
    cfg = load_agent_budget_config(_REPO)
    assert "caps" in cfg
    assert cfg["caps"]["daily_usd"] == 25.0


def test_daily_cap_usd():
    assert daily_cap_usd(load_agent_budget_config(_REPO)) == 25.0


def test_decide_transfer_spawn_when_headroom():
    snap = BudgetSnapshot(
        session_est_tokens=10_000,
        session_cap_tokens=200_000,
        daily_spent_usd=1.0,
        daily_cap_usd=25.0,
        monthly_spent_usd=10.0,
        monthly_cap_usd=400.0,
    )
    cfg = load_agent_budget_config(_REPO)
    assert decide_transfer(snap, cfg) == "spawn"
    assert snap.reasons


def test_decide_transfer_halt_monthly():
    snap = BudgetSnapshot(
        session_est_tokens=1000,
        daily_spent_usd=0,
        daily_cap_usd=25,
        monthly_spent_usd=500,
        monthly_cap_usd=400,
    )
    cfg = load_agent_budget_config(_REPO)
    assert decide_transfer(snap, cfg) == "halt_human"


def test_ledger_snapshot_writes_monthly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n  session_tokens: 100000\n  daily_usd: 10\n  monthly_usd: 50\n"
        "thresholds:\n  spawn_min_daily_remaining_pct: 15\n"
        "  spawn_min_monthly_remaining_pct: 10\n"
        "  handoff_only_below_session_pct: 80\n",
        encoding="utf-8",
    )
    ledger = BudgetLedger(tmp_path)
    snap = ledger.snapshot(session_tokens=5000)
    assert snap.session_est_tokens == 5000
    assert snap.decision in ("spawn", "handoff_only", "halt_human")
    assert (tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "monthly.json").is_file()


def test_router_daily_spend_in_snapshot(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n  daily_usd: 10\n  monthly_usd: 100\n  session_tokens: 100000\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "9.5")
    ledger = BudgetLedger(tmp_path)
    snap = ledger.snapshot(session_tokens=1000)
    assert snap.daily_spent_usd >= 9.5
