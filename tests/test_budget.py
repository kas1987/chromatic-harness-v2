"""Tests for 02_RUNTIME/budget/ledger.py — batch 1."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"
_MODULE_PATH = _RUNTIME / "budget" / "ledger.py"


def _load_module(monkeypatch) -> types.ModuleType:
    """Load budget.ledger via importlib, stubbing yaml if needed."""
    # yaml is stdlib-available via PyYAML; stub only if absent
    try:
        import yaml  # noqa: F401
    except ImportError:
        yaml_stub = types.ModuleType("yaml")
        yaml_stub.safe_load = lambda f: {}
        monkeypatch.setitem(sys.modules, "yaml", yaml_stub)

    spec = importlib.util.spec_from_file_location("budget.ledger", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["budget.ledger"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def budget_mod(monkeypatch):
    return _load_module(monkeypatch)


@pytest.fixture()
def ledger(budget_mod, tmp_path):
    """BudgetLedger rooted at tmp_path (no real FS side-effects)."""
    return budget_mod.BudgetLedger(repo_root=tmp_path)


@pytest.fixture()
def minimal_config():
    return {
        "caps": {
            "session_tokens": 200_000,
            "daily_usd": 25.0,
            "monthly_usd": 400.0,
        },
        "thresholds": {
            "spawn_min_daily_remaining_pct": 15,
            "spawn_min_monthly_remaining_pct": 10,
            "handoff_only_below_session_pct": 80,
        },
        "successor_reserve_usd": 2.0,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBudget:
    def test_import_clean(self, budget_mod):
        """Module imports cleanly; expected symbols present."""
        assert hasattr(budget_mod, "BudgetLedger")
        assert hasattr(budget_mod, "BudgetSnapshot")
        assert hasattr(budget_mod, "decide_transfer")
        assert hasattr(budget_mod, "load_agent_budget_config")
        assert hasattr(budget_mod, "daily_cap_usd")

    def test_budget_snapshot_defaults(self, budget_mod):
        """BudgetSnapshot has sane defaults and to_budget_dict works."""
        snap = budget_mod.BudgetSnapshot()
        d = snap.to_budget_dict()
        assert d["session_cap_tokens"] == 200_000
        assert d["daily_cap_usd"] == 25.0
        assert d["monthly_cap_usd"] == 400.0
        assert d["decision"] == "handoff_only"
        assert isinstance(d["reasons"], list)

    def test_decide_transfer_spawn_happy_path(self, budget_mod, minimal_config):
        """decide_transfer returns 'spawn' when all budgets are well under caps."""
        snap = budget_mod.BudgetSnapshot(
            session_est_tokens=50_000,
            session_cap_tokens=200_000,
            daily_spent_usd=1.0,
            daily_cap_usd=25.0,
            monthly_spent_usd=10.0,
            monthly_cap_usd=400.0,
        )
        result = budget_mod.decide_transfer(snap, minimal_config)
        assert result == "spawn"

    def test_decide_transfer_halt_on_monthly_cap(self, budget_mod, minimal_config):
        """decide_transfer returns 'halt_human' when monthly cap is reached."""
        snap = budget_mod.BudgetSnapshot(
            session_est_tokens=50_000,
            session_cap_tokens=200_000,
            daily_spent_usd=1.0,
            daily_cap_usd=25.0,
            monthly_spent_usd=400.0,  # at cap
            monthly_cap_usd=400.0,
        )
        result = budget_mod.decide_transfer(snap, minimal_config)
        assert result == "halt_human"

    def test_decide_transfer_halt_on_daily_cap(self, budget_mod, minimal_config):
        """decide_transfer returns 'halt_human' when daily cap is reached."""
        snap = budget_mod.BudgetSnapshot(
            session_est_tokens=50_000,
            session_cap_tokens=200_000,
            daily_spent_usd=25.0,  # at cap
            daily_cap_usd=25.0,
            monthly_spent_usd=30.0,
            monthly_cap_usd=400.0,
        )
        result = budget_mod.decide_transfer(snap, minimal_config)
        assert result == "halt_human"

    def test_decide_transfer_handoff_on_session_context(self, budget_mod, minimal_config):
        """decide_transfer returns 'handoff_only' when session tokens >= 80% cap."""
        snap = budget_mod.BudgetSnapshot(
            session_est_tokens=170_000,  # 85% of 200k -> above 80% threshold
            session_cap_tokens=200_000,
            daily_spent_usd=1.0,
            daily_cap_usd=25.0,
            monthly_spent_usd=10.0,
            monthly_cap_usd=400.0,
        )
        result = budget_mod.decide_transfer(snap, minimal_config)
        assert result == "handoff_only"
        assert any("session context" in r for r in snap.reasons)

    def test_daily_cap_usd_default(self, budget_mod):
        """daily_cap_usd returns 25.0 when config is empty."""
        cap = budget_mod.daily_cap_usd({})
        assert cap == 25.0

    def test_daily_cap_usd_from_config(self, budget_mod):
        """daily_cap_usd reads from caps.daily_usd in config."""
        cap = budget_mod.daily_cap_usd({"caps": {"daily_usd": 50.0}})
        assert cap == 50.0

    def test_load_agent_budget_config_missing_file(self, budget_mod, tmp_path):
        """load_agent_budget_config returns {} when config file is absent."""
        cfg = budget_mod.load_agent_budget_config(tmp_path)
        assert cfg == {}

    def test_load_agent_budget_config_reads_yaml(self, budget_mod, tmp_path):
        """load_agent_budget_config reads caps from a real yaml file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "agent_budget.yaml").write_text(
            "caps:\n  daily_usd: 42.0\n  monthly_usd: 500.0\n", encoding="utf-8"
        )
        cfg = budget_mod.load_agent_budget_config(tmp_path)
        assert cfg["caps"]["daily_usd"] == 42.0

    def test_ledger_append_daily_creates_file(self, ledger, tmp_path):
        """append_daily writes a JSONL record to the daily log."""
        ledger.append_daily(0.05, source="test", note="unit test")
        log_path = tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl"
        assert log_path.is_file()
        row = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert row["amount_usd"] == 0.05
        assert row["source"] == "test"

    def test_ledger_append_daily_multiple_rows(self, ledger, tmp_path):
        """append_daily accumulates multiple JSONL rows."""
        for i in range(3):
            ledger.append_daily(0.01 * (i + 1), source="loop")
        log_path = tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl"
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3

    def test_ledger_snapshot_returns_snapshot(self, ledger, budget_mod):
        """snapshot() returns a BudgetSnapshot instance."""
        snap = ledger.snapshot(session_tokens=10_000)
        assert isinstance(snap, budget_mod.BudgetSnapshot)
        assert snap.session_est_tokens == 10_000
        assert snap.decision in {"spawn", "handoff_only", "halt_human"}

    def test_ledger_snapshot_accounts_for_daily_spend(self, ledger, budget_mod):
        """snapshot() sums daily spend from the log file."""
        ledger.append_daily(5.0, source="router")
        ledger.append_daily(3.0, source="manual")
        snap = ledger.snapshot(session_tokens=1_000)
        # daily_spent_usd includes ledger entries (may also include env var 0)
        assert snap.daily_spent_usd >= 8.0

    def test_ingest_claude_usage_hook_missing_file(self, ledger):
        """ingest_claude_usage_hook returns 0.0 when drop file is absent."""
        result = ledger.ingest_claude_usage_hook()
        assert result == 0.0

    def test_ingest_claude_usage_hook_reads_cost(self, ledger, tmp_path):
        """ingest_claude_usage_hook reads session_cost_usd from drop file."""
        budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
        budget_dir.mkdir(parents=True)
        drop = budget_dir / "claude_usage_last.json"
        drop.write_text(json.dumps({"session_cost_usd": 1.23}), encoding="utf-8")
        result = ledger.ingest_claude_usage_hook()
        assert result == pytest.approx(1.23)

    def test_boundary_zero_budget_halts(self, budget_mod):
        """Zero caps immediately halt (both daily and monthly at cap)."""
        cfg = {
            "caps": {"session_tokens": 200_000, "daily_usd": 0.0, "monthly_usd": 0.0},
            "thresholds": {},
            "successor_reserve_usd": 0.0,
        }
        snap = budget_mod.BudgetSnapshot(daily_spent_usd=0.0, monthly_spent_usd=0.0)
        result = budget_mod.decide_transfer(snap, cfg)
        assert result == "halt_human"

    def test_fail_open_empty_config(self, budget_mod):
        """decide_transfer with empty config uses BudgetSnapshot defaults and doesn't raise."""
        snap = budget_mod.BudgetSnapshot(
            session_est_tokens=10_000,
            session_cap_tokens=200_000,
            daily_spent_usd=1.0,
            daily_cap_usd=25.0,
            monthly_spent_usd=5.0,
            monthly_cap_usd=400.0,
        )
        result = budget_mod.decide_transfer(snap, {})
        assert result in {"spawn", "handoff_only", "halt_human"}
