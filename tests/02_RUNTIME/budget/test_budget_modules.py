"""Comprehensive tests for 02_RUNTIME/budget/*.

Covers ledger.py, quota_proxy.py, quota_state.py, and transfer_packet.py.
All external I/O (file writes, DB, network) is mocked.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# sys.path bootstrap — required per project rules
# ---------------------------------------------------------------------------
_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget import quota_proxy  # noqa: E402
from budget.ledger import (  # noqa: E402
    BudgetLedger,
    BudgetSnapshot,
    daily_cap_usd,
    decide_transfer,
    load_agent_budget_config,
)
from budget.quota_state import (  # noqa: E402
    EMPTY_STATE,
    MANUAL_SEED_TTL_SECONDS,
    STALENESS_SECONDS,
    QuotaState,
    QuotaStateReader,
    read_quota_state,
)
from budget.transfer_packet import (  # noqa: E402
    build_transfer_packet,
    write_successor_prompt,
    write_transfer_artifacts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_CONFIG = """
caps:
  session_tokens: 200000
  daily_usd: 25.0
  monthly_usd: 400.0
thresholds:
  spawn_min_daily_remaining_pct: 15
  spawn_min_monthly_remaining_pct: 10
  handoff_only_below_session_pct: 80
successor_reserve_usd: 2.0
"""

_TIGHT_CONFIG = """
caps:
  session_tokens: 100000
  daily_usd: 10.0
  monthly_usd: 50.0
thresholds:
  spawn_min_daily_remaining_pct: 15
  spawn_min_monthly_remaining_pct: 10
  handoff_only_below_session_pct: 80
successor_reserve_usd: 2.0
boot_commands:
  - bd ready
"""


def _write_config(tmp_path: Path, content: str = _MINIMAL_CONFIG) -> Path:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(exist_ok=True)
    cfg_file = cfg_dir / "agent_budget.yaml"
    cfg_file.write_text(content, encoding="utf-8")
    return cfg_file


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _fresh_ts() -> str:
    return _iso(datetime.now(timezone.utc))


def _stale_ts(seconds: int = STALENESS_SECONDS + 60) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(seconds=seconds))


def _fresh_snap(**kwargs) -> BudgetSnapshot:
    defaults = dict(
        session_est_tokens=10_000,
        session_cap_tokens=200_000,
        daily_spent_usd=1.0,
        daily_cap_usd=25.0,
        monthly_spent_usd=10.0,
        monthly_cap_usd=400.0,
        decision="spawn",
        reasons=["budget headroom OK for successor spawn"],
    )
    defaults.update(kwargs)
    return BudgetSnapshot(**defaults)


# ---------------------------------------------------------------------------
# ledger.py — load_agent_budget_config
# ---------------------------------------------------------------------------


class TestLoadAgentBudgetConfig:
    def test_returns_empty_dict_when_no_config_file(self, tmp_path):
        cfg = load_agent_budget_config(tmp_path)
        assert cfg == {}

    def test_loads_minimal_yaml(self, tmp_path):
        _write_config(tmp_path)
        cfg = load_agent_budget_config(tmp_path)
        assert "caps" in cfg
        assert cfg["caps"]["daily_usd"] == 25.0

    def test_loads_monthly_cap(self, tmp_path):
        _write_config(tmp_path)
        cfg = load_agent_budget_config(tmp_path)
        assert cfg["caps"]["monthly_usd"] == 400.0

    def test_loads_thresholds(self, tmp_path):
        _write_config(tmp_path)
        cfg = load_agent_budget_config(tmp_path)
        assert cfg["thresholds"]["spawn_min_daily_remaining_pct"] == 15

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "agent_budget.yaml").write_text("", encoding="utf-8")
        cfg = load_agent_budget_config(tmp_path)
        assert cfg == {}


# ---------------------------------------------------------------------------
# ledger.py — daily_cap_usd
# ---------------------------------------------------------------------------


class TestDailyCapUsd:
    def test_returns_default_when_no_config(self):
        assert daily_cap_usd({}) == 25.0

    def test_reads_from_config(self, tmp_path):
        _write_config(tmp_path)
        cfg = load_agent_budget_config(tmp_path)
        assert daily_cap_usd(cfg) == 25.0

    def test_custom_cap(self):
        assert daily_cap_usd({"caps": {"daily_usd": 50.0}}) == 50.0

    def test_caps_none_falls_back_to_default(self):
        assert daily_cap_usd({"caps": None}) == 25.0


# ---------------------------------------------------------------------------
# ledger.py — BudgetSnapshot
# ---------------------------------------------------------------------------


class TestBudgetSnapshot:
    def test_default_values(self):
        snap = BudgetSnapshot()
        assert snap.session_est_tokens == 0
        assert snap.session_cap_tokens == 200_000
        assert snap.daily_spent_usd == 0.0
        assert snap.daily_cap_usd == 25.0
        assert snap.monthly_spent_usd == 0.0
        assert snap.monthly_cap_usd == 400.0
        assert snap.decision == "handoff_only"
        assert snap.reasons == []

    def test_to_budget_dict_keys(self):
        snap = BudgetSnapshot()
        d = snap.to_budget_dict()
        expected = {
            "session_est_tokens",
            "session_cap_tokens",
            "daily_spent_usd",
            "daily_cap_usd",
            "monthly_spent_usd",
            "monthly_cap_usd",
            "decision",
            "reasons",
        }
        assert set(d.keys()) == expected

    def test_to_budget_dict_rounds_usd(self):
        snap = BudgetSnapshot(daily_spent_usd=1.23456789)
        d = snap.to_budget_dict()
        assert d["daily_spent_usd"] == round(1.23456789, 4)

    def test_to_budget_dict_monthly_rounded(self):
        snap = BudgetSnapshot(monthly_spent_usd=99.999999)
        d = snap.to_budget_dict()
        assert d["monthly_spent_usd"] == round(99.999999, 4)

    def test_custom_values_roundtrip(self):
        snap = BudgetSnapshot(
            session_est_tokens=50_000,
            daily_spent_usd=5.0,
            monthly_spent_usd=100.0,
            decision="spawn",
            reasons=["ok"],
        )
        d = snap.to_budget_dict()
        assert d["session_est_tokens"] == 50_000
        assert d["decision"] == "spawn"
        assert d["reasons"] == ["ok"]


# ---------------------------------------------------------------------------
# ledger.py — decide_transfer
# ---------------------------------------------------------------------------


class TestDecideTransfer:
    def _cfg(self, **overrides) -> dict:
        base = {
            "caps": {"session_tokens": 200_000, "daily_usd": 25.0, "monthly_usd": 400.0},
            "thresholds": {
                "spawn_min_daily_remaining_pct": 15,
                "spawn_min_monthly_remaining_pct": 10,
                "handoff_only_below_session_pct": 80,
            },
            "successor_reserve_usd": 2.0,
        }
        base.update(overrides)
        return base

    def test_spawn_when_ample_headroom(self):
        snap = _fresh_snap()
        result = decide_transfer(snap, self._cfg())
        assert result == "spawn"
        assert snap.reasons

    def test_halt_when_monthly_cap_exceeded(self):
        snap = _fresh_snap(monthly_spent_usd=401.0, monthly_cap_usd=400.0)
        result = decide_transfer(snap, self._cfg())
        assert result == "halt_human"
        assert any("monthly cap" in r for r in snap.reasons)

    def test_halt_when_daily_cap_exceeded(self):
        snap = _fresh_snap(daily_spent_usd=25.0, daily_cap_usd=25.0)
        result = decide_transfer(snap, self._cfg())
        assert result == "halt_human"
        assert any("daily cap" in r for r in snap.reasons)

    def test_halt_exact_monthly_boundary(self):
        snap = _fresh_snap(monthly_spent_usd=400.0, monthly_cap_usd=400.0)
        result = decide_transfer(snap, self._cfg())
        assert result == "halt_human"

    def test_halt_exact_daily_boundary(self):
        snap = _fresh_snap(daily_spent_usd=25.0, daily_cap_usd=25.0)
        result = decide_transfer(snap, self._cfg())
        assert result == "halt_human"

    def test_handoff_when_session_tokens_high(self):
        snap = _fresh_snap(
            session_est_tokens=180_000,
            session_cap_tokens=200_000,
        )
        result = decide_transfer(snap, self._cfg())
        assert result == "handoff_only"
        assert any("session context high" in r for r in snap.reasons)

    def test_handoff_when_daily_headroom_low(self):
        # daily remaining = 25 - 22 = 3, need 15% of 25 = 3.75 + reserve 2 = 5.75
        snap = _fresh_snap(daily_spent_usd=22.0, daily_cap_usd=25.0)
        result = decide_transfer(snap, self._cfg())
        assert result == "handoff_only"
        assert any("daily headroom" in r for r in snap.reasons)

    def test_handoff_when_monthly_headroom_low(self):
        # monthly remaining = 400 - 390 = 10, need 10% of 400 = 40 + reserve 2 = 42
        snap = _fresh_snap(monthly_spent_usd=390.0, monthly_cap_usd=400.0)
        result = decide_transfer(snap, self._cfg())
        assert result in ("handoff_only", "halt_human")

    def test_reasons_populated_on_spawn(self):
        snap = _fresh_snap()
        decide_transfer(snap, self._cfg())
        assert len(snap.reasons) >= 1

    def test_reasons_populated_on_halt(self):
        snap = _fresh_snap(monthly_spent_usd=500.0)
        decide_transfer(snap, self._cfg())
        assert len(snap.reasons) >= 1

    def test_uses_config_caps_over_snapshot_defaults(self):
        # Config caps take precedence
        snap = _fresh_snap(daily_spent_usd=9.0, daily_cap_usd=25.0)
        cfg = self._cfg()
        cfg["caps"]["daily_usd"] = 10.0  # tight cap
        result = decide_transfer(snap, cfg)
        # 10 - 9 = 1 remaining, need 1.5 + 2 = 3.5 → headroom low → handoff
        assert result == "handoff_only"

    def test_zero_session_cap_handled(self):
        snap = _fresh_snap(session_cap_tokens=0)
        result = decide_transfer(snap, self._cfg())
        assert result in ("spawn", "handoff_only", "halt_human")


# ---------------------------------------------------------------------------
# ledger.py — BudgetLedger
# ---------------------------------------------------------------------------


class TestBudgetLedger:
    def test_ledger_initializes_with_repo_root(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        assert ledger.repo_root == tmp_path.resolve()

    def test_ledger_missing_config_uses_defaults(self, tmp_path):
        ledger = BudgetLedger(tmp_path)
        assert ledger.config == {}

    def test_append_daily_creates_log_file(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.append_daily(1.5, source="test", note="hello")
        assert ledger.daily_log.is_file()

    def test_append_daily_valid_json_lines(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.append_daily(2.0, source="router", note="run")
        ledger.append_daily(3.0, source="transfer")
        lines = ledger.daily_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            row = json.loads(line)
            assert "timestamp" in row
            assert "amount_usd" in row
            assert "source" in row

    def test_append_daily_decision_id(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.append_daily(1.0, source="test", decision_id="abc-123")
        row = json.loads(ledger.daily_log.read_text(encoding="utf-8").strip())
        assert row["decision_id"] == "abc-123"

    def test_append_daily_no_decision_id_field_when_empty(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.append_daily(1.0, source="test")
        row = json.loads(ledger.daily_log.read_text(encoding="utf-8").strip())
        assert "decision_id" not in row

    def test_snapshot_returns_budget_snapshot(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        snap = ledger.snapshot(session_tokens=5_000)
        assert isinstance(snap, BudgetSnapshot)
        assert snap.session_est_tokens == 5_000

    def test_snapshot_writes_monthly_file(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.snapshot(session_tokens=1_000)
        assert ledger.monthly_file.is_file()

    def test_snapshot_monthly_file_valid_json(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.snapshot(session_tokens=1_000)
        data = json.loads(ledger.monthly_file.read_text(encoding="utf-8"))
        assert "months" in data
        assert "updated_at" in data

    def test_snapshot_extra_daily_usd_added(self, tmp_path, monkeypatch):
        _write_config(tmp_path)
        monkeypatch.delenv("CHROMATIC_ROUTER_DAILY_SPEND", raising=False)
        ledger = BudgetLedger(tmp_path)
        snap = ledger.snapshot(session_tokens=1_000, extra_daily_usd=5.0)
        assert snap.daily_spent_usd >= 5.0

    def test_snapshot_uses_router_env_spend(self, tmp_path, monkeypatch):
        _write_config(tmp_path)
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "8.0")
        ledger = BudgetLedger(tmp_path)
        snap = ledger.snapshot(session_tokens=1_000)
        assert snap.daily_spent_usd >= 8.0

    def test_snapshot_decision_is_valid(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        snap = ledger.snapshot(session_tokens=1_000)
        assert snap.decision in ("spawn", "handoff_only", "halt_human")

    def test_snapshot_accumulates_daily_spend(self, tmp_path, monkeypatch):
        _write_config(tmp_path)
        monkeypatch.delenv("CHROMATIC_ROUTER_DAILY_SPEND", raising=False)
        ledger = BudgetLedger(tmp_path)
        ledger.append_daily(2.0, source="test1")
        ledger.append_daily(3.0, source="test2")
        snap = ledger.snapshot(session_tokens=1_000)
        assert snap.daily_spent_usd >= 5.0

    def test_estimate_session_tokens_returns_int(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        tokens = ledger.estimate_session_tokens()
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_session_tokens_from_manifest(self, tmp_path):
        _write_config(tmp_path)
        manifest_dir = tmp_path / "07_LOGS_AND_AUDIT" / "pre_session"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "latest.json").write_text(json.dumps({"estimated_tokens": 42_000}), encoding="utf-8")
        ledger = BudgetLedger(tmp_path)
        assert ledger.estimate_session_tokens() == 42_000

    def test_estimate_session_tokens_from_audit(self, tmp_path):
        _write_config(tmp_path)
        audit_dir = tmp_path / ".agents" / "audits"
        audit_dir.mkdir(parents=True)
        (audit_dir / "latest_audit.json").write_text(
            json.dumps({"estimated_tokens": 33_000, "Estimate:": True}),
            encoding="utf-8",
        )
        ledger = BudgetLedger(tmp_path)
        assert ledger.estimate_session_tokens() == 33_000

    def test_estimate_session_tokens_from_activity_log(self, tmp_path):
        _write_config(tmp_path)
        activity_dir = tmp_path / "07_LOGS_AND_AUDIT" / "activity"
        activity_dir.mkdir(parents=True)
        lines = "\n".join([json.dumps({"event": "x"}) for _ in range(10)])
        (activity_dir / "agent_activity.jsonl").write_text(lines, encoding="utf-8")
        ledger = BudgetLedger(tmp_path)
        est = ledger.estimate_session_tokens()
        assert est == min(50_000, 10 * 500)

    def test_estimate_session_tokens_default_when_no_sources(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        assert ledger.estimate_session_tokens() == 25_000

    def test_ingest_claude_usage_hook_missing_file(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        assert ledger.ingest_claude_usage_hook() == 0.0

    def test_ingest_claude_usage_hook_reads_cost(self, tmp_path):
        _write_config(tmp_path)
        budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
        budget_dir.mkdir(parents=True)
        (budget_dir / "claude_usage_last.json").write_text(json.dumps({"session_cost_usd": 7.5}), encoding="utf-8")
        ledger = BudgetLedger(tmp_path)
        assert ledger.ingest_claude_usage_hook() == 7.5

    def test_ingest_claude_usage_hook_bad_json_returns_zero(self, tmp_path):
        _write_config(tmp_path)
        budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
        budget_dir.mkdir(parents=True)
        (budget_dir / "claude_usage_last.json").write_text("not-json", encoding="utf-8")
        ledger = BudgetLedger(tmp_path)
        assert ledger.ingest_claude_usage_hook() == 0.0

    def test_monthly_rollup_written_and_re_read(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.snapshot(session_tokens=1_000)
        # Second snapshot reads rollup from the file
        snap2 = ledger.snapshot(session_tokens=1_000)
        assert snap2.monthly_spent_usd >= 0.0

    def test_monthly_file_corrupt_fallback(self, tmp_path):
        _write_config(tmp_path)
        ledger = BudgetLedger(tmp_path)
        ledger.budget_dir.mkdir(parents=True, exist_ok=True)
        ledger.monthly_file.write_text("not-json", encoding="utf-8")
        # Should not raise; fallback to daily ledger sum
        snap = ledger.snapshot(session_tokens=1_000)
        assert snap.monthly_spent_usd >= 0.0

    def test_router_daily_spend_invalid_env_returns_zero(self, tmp_path, monkeypatch):
        _write_config(tmp_path)
        monkeypatch.setenv("CHROMATIC_ROUTER_DAILY_SPEND", "not-a-float")
        ledger = BudgetLedger(tmp_path)
        snap = ledger.snapshot(session_tokens=1_000)
        # Still returns a valid snapshot
        assert isinstance(snap, BudgetSnapshot)


# ---------------------------------------------------------------------------
# quota_proxy.py — _to_pct
# ---------------------------------------------------------------------------


class TestToPct:
    def test_none_input(self):
        assert quota_proxy._to_pct(None) is None

    def test_fraction_to_percent(self):
        assert quota_proxy._to_pct("0.875") == 87.5

    def test_fraction_zero(self):
        assert quota_proxy._to_pct("0.0") == 0.0

    def test_fraction_one(self):
        assert quota_proxy._to_pct("1.0") == 100.0

    def test_percent_form(self):
        assert quota_proxy._to_pct("42") == 42.0

    def test_percent_with_symbol(self):
        assert quota_proxy._to_pct("42%") == 42.0

    def test_non_numeric_returns_none(self):
        assert quota_proxy._to_pct("bad") is None

    def test_large_value_not_multiplied(self):
        result = quota_proxy._to_pct("75.5")
        assert result == 75.5

    def test_small_fraction_rounded(self):
        result = quota_proxy._to_pct("0.10")
        assert result is not None
        assert abs(result - 10.0) < 0.01


# ---------------------------------------------------------------------------
# quota_proxy.py — _get_ci
# ---------------------------------------------------------------------------


class TestGetCi:
    class _Hdrs:
        def __init__(self, d):
            self._d = {k.lower(): v for k, v in d.items()}

        def getheader(self, name, default=None):
            return self._d.get(name.lower(), default)

    def test_getheader_path(self):
        h = self._Hdrs({"X-Foo": "bar"})
        assert quota_proxy._get_ci(h, "x-foo") == "bar"

    def test_case_insensitive(self):
        h = self._Hdrs({"Content-Type": "text/plain"})
        assert quota_proxy._get_ci(h, "content-type") == "text/plain"

    def test_missing_returns_none(self):
        h = self._Hdrs({})
        assert quota_proxy._get_ci(h, "x-missing") is None

    def test_dict_fallback(self):
        d = {"X-Test": "value"}
        assert quota_proxy._get_ci(d, "X-Test") == "value"

    def test_exception_returns_none(self):
        result = quota_proxy._get_ci(object(), "x-foo")
        assert result is None


# ---------------------------------------------------------------------------
# quota_proxy.py — parse_quota_headers
# ---------------------------------------------------------------------------


class _FakeHeaders:
    def __init__(self, mapping: dict[str, str]):
        self._m = {k.lower(): v for k, v in mapping.items()}

    def getheader(self, name: str, default=None):
        return self._m.get(name.lower(), default)


class TestParseQuotaHeaders:
    def test_full_header_set_fraction(self):
        h = _FakeHeaders(
            {
                "anthropic-ratelimit-unified-7d-utilization": "0.875",
                "anthropic-ratelimit-unified-5h-utilization": "0.10",
                "anthropic-ratelimit-unified-7d-reset": "2026-06-02T00:00:00Z",
                "anthropic-ratelimit-unified-5h-reset": "2026-05-30T18:00:00Z",
                "anthropic-ratelimit-unified-status": "allowed",
                "anthropic-ratelimit-unified-representative-claim": "claim-xyz",
            }
        )
        rec = quota_proxy.parse_quota_headers(h)
        assert rec["weekly_pct"] == 87.5
        assert rec["session_5h_pct"] == 10.0
        assert rec["status"] == "allowed"
        assert rec["representative_claim"] == "claim-xyz"
        assert rec["weekly_reset"] == "2026-06-02T00:00:00Z"
        assert rec["source"] == "proxy"
        assert rec["captured_at"]

    def test_percent_form_headers(self):
        h = _FakeHeaders({"anthropic-ratelimit-unified-7d-utilization": "42"})
        rec = quota_proxy.parse_quota_headers(h)
        assert rec["weekly_pct"] == 42.0

    def test_empty_headers_all_none(self):
        rec = quota_proxy.parse_quota_headers(_FakeHeaders({}))
        assert rec["weekly_pct"] is None
        assert rec["session_5h_pct"] is None
        assert rec["status"] is None
        assert rec["representative_claim"] is None

    def test_captured_at_is_iso_format(self):
        rec = quota_proxy.parse_quota_headers(_FakeHeaders({}))
        assert "T" in rec["captured_at"]

    def test_partial_headers(self):
        h = _FakeHeaders({"anthropic-ratelimit-unified-status": "throttled"})
        rec = quota_proxy.parse_quota_headers(h)
        assert rec["status"] == "throttled"
        assert rec["weekly_pct"] is None

    def test_bad_utilization_value_maps_to_none(self):
        h = _FakeHeaders({"anthropic-ratelimit-unified-7d-utilization": "not-a-num"})
        rec = quota_proxy.parse_quota_headers(h)
        assert rec["weekly_pct"] is None


# ---------------------------------------------------------------------------
# quota_proxy.py — write_quota_state / _has_any_signal
# ---------------------------------------------------------------------------


class TestWriteQuotaState:
    def test_writes_file_atomically(self, tmp_path):
        path = tmp_path / "quota_state.json"
        rec = {"weekly_pct": 80.0, "source": "proxy", "captured_at": _fresh_ts()}
        assert quota_proxy.write_quota_state(rec, path) is True
        assert path.is_file()

    def test_written_file_is_valid_json(self, tmp_path):
        path = tmp_path / "quota_state.json"
        rec = {"weekly_pct": 55.0, "captured_at": _fresh_ts()}
        quota_proxy.write_quota_state(rec, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["weekly_pct"] == 55.0

    def test_returns_false_on_permission_error(self, tmp_path):
        path = tmp_path / "no_dir" / "sub" / "quota_state.json"
        # Force OSError by making parent a file
        blocker = tmp_path / "no_dir"
        blocker.write_text("file", encoding="utf-8")
        result = quota_proxy.write_quota_state({"x": 1}, path)
        assert result is False

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "state.json"
        result = quota_proxy.write_quota_state({"weekly_pct": 10.0}, path)
        assert result is True
        assert path.is_file()


class TestHasAnySignal:
    def test_weekly_pct_gives_signal(self):
        assert quota_proxy._has_any_signal({"weekly_pct": 50.0}) is True

    def test_status_gives_signal(self):
        assert quota_proxy._has_any_signal({"status": "allowed"}) is True

    def test_session_5h_pct_gives_signal(self):
        assert quota_proxy._has_any_signal({"session_5h_pct": 10.0}) is True

    def test_representative_claim_gives_signal(self):
        assert quota_proxy._has_any_signal({"representative_claim": "x"}) is True

    def test_all_none_no_signal(self):
        assert quota_proxy._has_any_signal({"weekly_pct": None, "status": None}) is False

    def test_empty_dict_no_signal(self):
        assert quota_proxy._has_any_signal({}) is False


# ---------------------------------------------------------------------------
# quota_proxy.py — build_server
# ---------------------------------------------------------------------------


class TestBuildServer:
    def test_builds_without_binding_real_port(self):
        server = quota_proxy.build_server(0, host="127.0.0.1")
        try:
            assert server.server_address[0] == "127.0.0.1"
        finally:
            server.server_close()

    def test_custom_state_path_set_on_handler(self, tmp_path):
        path = tmp_path / "my_state.json"
        server = quota_proxy.build_server(0, state_path=path)
        try:
            assert server.RequestHandlerClass.state_path == path
        finally:
            server.server_close()

    def test_default_state_path_when_none(self):
        server = quota_proxy.build_server(0)
        try:
            assert server.RequestHandlerClass.state_path == quota_proxy.DEFAULT_STATE_PATH
        finally:
            server.server_close()


# ---------------------------------------------------------------------------
# quota_proxy.py — proxy + write roundtrip
# ---------------------------------------------------------------------------


class TestProxyWriteStateRoundtrip:
    def test_roundtrip_proxy_to_reader(self, tmp_path):
        h = _FakeHeaders(
            {
                "anthropic-ratelimit-unified-7d-utilization": "0.9",
                "anthropic-ratelimit-unified-status": "allowed",
            }
        )
        rec = quota_proxy.parse_quota_headers(h)
        path = tmp_path / "quota_state.json"
        quota_proxy.write_quota_state(rec, path)

        state = QuotaStateReader(path).read()
        assert state.weekly_pct == 90.0
        assert state.status == "allowed"
        assert state.is_fresh() is True


# ---------------------------------------------------------------------------
# quota_state.py — QuotaState dataclass
# ---------------------------------------------------------------------------


class TestQuotaState:
    def test_default_state_not_present(self):
        s = QuotaState()
        assert s.present is False
        assert s.source == "unknown"

    def test_from_dict_full_record(self):
        ts = _fresh_ts()
        state = QuotaState.from_dict(
            {
                "weekly_pct": 87.5,
                "weekly_reset": "2026-06-02T00:00:00+00:00",
                "session_5h_pct": "12.0",
                "session_5h_reset": "2026-05-30T18:00:00+00:00",
                "representative_claim": "claim-abc",
                "status": "allowed",
                "captured_at": ts,
                "source": "proxy",
            }
        )
        assert state.present is True
        assert state.weekly_pct == 87.5
        assert state.session_5h_pct == 12.0
        assert state.representative_claim == "claim-abc"
        assert state.source == "proxy"

    def test_from_dict_partial_record(self):
        state = QuotaState.from_dict({"weekly_pct": 50, "captured_at": _fresh_ts()})
        assert state.weekly_pct == 50.0
        assert state.session_5h_pct is None
        assert state.present is True

    def test_from_dict_bad_pct_is_none(self):
        state = QuotaState.from_dict({"weekly_pct": "not-a-number"})
        assert state.weekly_pct is None

    def test_from_dict_stores_raw(self):
        data = {"weekly_pct": 10, "captured_at": _fresh_ts()}
        state = QuotaState.from_dict(data)
        assert state.raw == data

    def test_age_seconds_fresh(self):
        ts = datetime.now(timezone.utc) - timedelta(seconds=30)
        state = QuotaState.from_dict({"weekly_pct": 10, "captured_at": _iso(ts)})
        age = state.age_seconds()
        assert age is not None
        assert 25 <= age <= 60

    def test_age_seconds_missing_captured_at(self):
        state = QuotaState.from_dict({"weekly_pct": 10})
        assert state.age_seconds() is None

    def test_is_fresh_within_window(self):
        ts = datetime.now(timezone.utc) - timedelta(seconds=10)
        state = QuotaState.from_dict({"weekly_pct": 80, "captured_at": _iso(ts)})
        assert state.is_fresh() is True

    def test_is_fresh_beyond_window(self):
        ts = datetime.now(timezone.utc) - timedelta(seconds=STALENESS_SECONDS + 10)
        state = QuotaState.from_dict({"weekly_pct": 80, "captured_at": _iso(ts)})
        assert state.is_fresh() is False

    def test_is_fresh_custom_max_age(self):
        ts = datetime.now(timezone.utc) - timedelta(seconds=10)
        state = QuotaState.from_dict({"weekly_pct": 80, "captured_at": _iso(ts)})
        assert state.is_fresh(max_age_seconds=5) is False
        assert state.is_fresh(max_age_seconds=60) is True

    def test_is_fresh_not_present(self):
        state = QuotaState(present=False)
        assert state.is_fresh() is False

    def test_z_suffix_timestamp_parsed(self):
        ts = datetime.now(timezone.utc) - timedelta(seconds=10)
        z = ts.replace(tzinfo=None).isoformat() + "Z"
        state = QuotaState.from_dict({"weekly_pct": 90, "captured_at": z})
        assert state.is_fresh() is True

    def test_to_dict_keys(self):
        state = QuotaState.from_dict({"weekly_pct": 50, "captured_at": _fresh_ts()})
        d = state.to_dict()
        expected = {
            "weekly_pct",
            "weekly_reset",
            "session_5h_pct",
            "session_5h_reset",
            "representative_claim",
            "status",
            "captured_at",
            "source",
        }
        assert set(d.keys()) == expected

    def test_to_dict_values_match(self):
        ts = _fresh_ts()
        state = QuotaState.from_dict({"weekly_pct": 72.0, "captured_at": ts, "status": "ok"})
        d = state.to_dict()
        assert d["weekly_pct"] == 72.0
        assert d["status"] == "ok"
        assert d["captured_at"] == ts


# ---------------------------------------------------------------------------
# quota_state.py — EMPTY_STATE constant
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_not_present(self):
        assert EMPTY_STATE.present is False

    def test_source_is_absent(self):
        assert EMPTY_STATE.source == "absent"

    def test_not_fresh(self):
        assert EMPTY_STATE.is_fresh() is False

    def test_weekly_pct_none(self):
        assert EMPTY_STATE.weekly_pct is None


# ---------------------------------------------------------------------------
# quota_state.py — QuotaStateReader
# ---------------------------------------------------------------------------


class TestQuotaStateReader:
    def test_reads_fresh_file(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text(
            json.dumps({"weekly_pct": 88.0, "captured_at": _fresh_ts(), "source": "proxy"}),
            encoding="utf-8",
        )
        reader = QuotaStateReader(path)
        state = reader.read()
        assert state.weekly_pct == 88.0
        assert state.present is True

    def test_missing_file_fails_open(self, tmp_path):
        reader = QuotaStateReader(tmp_path / "nope.json")
        state = reader.read()
        assert state.present is False

    def test_malformed_json_fails_open(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text("{ bad json", encoding="utf-8")
        reader = QuotaStateReader(path)
        assert reader.read().present is False

    def test_non_dict_json_fails_open(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        reader = QuotaStateReader(path)
        assert reader.read().present is False

    def test_read_fresh_returns_none_when_stale(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text(
            json.dumps({"weekly_pct": 88.0, "captured_at": _stale_ts()}),
            encoding="utf-8",
        )
        reader = QuotaStateReader(path)
        assert reader.read_fresh() is None

    def test_read_fresh_returns_state_when_fresh(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text(
            json.dumps({"weekly_pct": 88.0, "captured_at": _fresh_ts()}),
            encoding="utf-8",
        )
        reader = QuotaStateReader(path)
        assert reader.read_fresh() is not None

    def test_is_stale_true_when_missing(self, tmp_path):
        reader = QuotaStateReader(tmp_path / "missing.json")
        assert reader.is_stale() is True

    def test_is_stale_false_when_fresh(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text(
            json.dumps({"weekly_pct": 50, "captured_at": _fresh_ts()}),
            encoding="utf-8",
        )
        reader = QuotaStateReader(path)
        assert reader.is_stale() is False

    def test_custom_max_age_seconds(self, tmp_path):
        path = tmp_path / "qs.json"
        ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        path.write_text(
            json.dumps({"weekly_pct": 50, "captured_at": _iso(ts)}),
            encoding="utf-8",
        )
        # Fresh with 600s TTL, stale with 300s TTL
        reader_long = QuotaStateReader(path, max_age_seconds=600)
        reader_short = QuotaStateReader(path, max_age_seconds=300)
        assert reader_long.is_stale() is False
        assert reader_short.is_stale() is True

    def test_accepts_string_path(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text(
            json.dumps({"weekly_pct": 10, "captured_at": _fresh_ts()}),
            encoding="utf-8",
        )
        reader = QuotaStateReader(str(path))
        assert reader.read().weekly_pct == 10.0

    def test_manual_seed_ttl_constant_exists(self):
        assert MANUAL_SEED_TTL_SECONDS == 86400


# ---------------------------------------------------------------------------
# quota_state.py — read_quota_state convenience function
# ---------------------------------------------------------------------------


class TestReadQuotaStateConvenience:
    def test_reads_present_file(self, tmp_path):
        path = tmp_path / "qs.json"
        path.write_text(
            json.dumps({"weekly_pct": 12.5, "captured_at": _fresh_ts()}),
            encoding="utf-8",
        )
        state = read_quota_state(path)
        assert state.weekly_pct == 12.5

    def test_missing_file_returns_empty(self, tmp_path):
        state = read_quota_state(tmp_path / "nope.json")
        assert state.present is False

    def test_accepts_custom_max_age(self, tmp_path):
        path = tmp_path / "qs.json"
        ts = _iso(datetime.now(timezone.utc) - timedelta(seconds=10))
        path.write_text(
            json.dumps({"weekly_pct": 5, "captured_at": ts}),
            encoding="utf-8",
        )
        state = read_quota_state(path, max_age_seconds=5)
        # State is still read (read doesn't filter by age), just present
        assert state.present is True


# ---------------------------------------------------------------------------
# transfer_packet.py — build_transfer_packet
# ---------------------------------------------------------------------------


class TestBuildTransferPacket:
    def test_returns_dict_with_required_keys(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
        )
        required = {
            "transfer_id",
            "updated_at",
            "source_runtime",
            "objective",
            "decision",
            "summary",
            "successor",
            "budget",
            "boot_commands",
            "forbidden",
            "handoff_path",
            "latest_pointer",
        }
        assert required.issubset(set(packet.keys()))

    def test_transfer_id_is_uuid(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="cursor", snapshot=snap)
        # Must be parseable as UUID
        parsed = uuid.UUID(packet["transfer_id"])
        assert str(parsed) == packet["transfer_id"]

    def test_source_runtime_set(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="vscode", snapshot=snap)
        assert packet["source_runtime"] == "vscode"

    def test_budget_dict_embedded(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap(daily_spent_usd=3.5)
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["budget"]["daily_spent_usd"] == round(3.5, 4)
        assert "decision" in packet["budget"]

    def test_spawn_mode_auto_when_spawn_decision(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap(decision="spawn")
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["successor"]["spawn_mode"] == "auto"

    def test_spawn_mode_manual_when_handoff_only(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap(decision="handoff_only")
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["successor"]["spawn_mode"] == "manual"

    def test_spawn_mode_manual_when_halt_human(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap(decision="halt_human")
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["successor"]["spawn_mode"] == "manual"

    def test_objective_from_handoff_prep(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            handoff_prep={"context_snapshot": {"objective": "Fix the bug"}},
        )
        assert packet["objective"] == "Fix the bug"

    def test_objective_default_when_missing(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert "Resume harness work" in packet["objective"]

    def test_next_action_from_goals(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            handoff_prep={"next_session_goals": ["run tests", "ship feature"]},
        )
        assert packet["next_action"] == "run tests"

    def test_next_action_default(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["next_action"] == "bd ready"

    def test_git_snapshot_included_when_provided(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        git_info = {"branch": "main", "sha": "abc123"}
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            git_snapshot=git_info,
        )
        assert packet["git"] == git_info

    def test_no_git_key_when_not_provided(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert "git" not in packet

    def test_forbidden_list_present(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert "full_transcript" in packet["forbidden"]
        assert "bulk_jsonl_scan" in packet["forbidden"]

    def test_beads_ready_defaults_empty(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["beads_ready"] == []

    def test_beads_ready_populated(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            beads_ready=["task-1", "task-2"],
        )
        assert packet["beads_ready"] == ["task-1", "task-2"]

    def test_boot_commands_from_config(self, tmp_path):
        _write_config(tmp_path, _TIGHT_CONFIG)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert "bd ready" in packet["boot_commands"]

    def test_successor_runtime_from_env(self, tmp_path, monkeypatch):
        _write_config(tmp_path)
        monkeypatch.setenv("CHROMATIC_SUCCESSOR_RUNTIME", "gemini")
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["successor"]["runtime"] == "gemini"

    def test_confidence_default(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert packet["confidence"] == 70

    def test_confidence_from_handoff_prep(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            handoff_prep={"confidence": 90},
        )
        assert packet["confidence"] == 90

    def test_risks_default_includes_budget_decision(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap(decision="handoff_only")
        packet = build_transfer_packet(tmp_path, source_runtime="claude", snapshot=snap)
        assert any("handoff_only" in r for r in packet["risks"])

    def test_summary_from_handoff_prep(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            handoff_prep={"directive_summary": "Did important work"},
        )
        assert "Did important work" in packet["summary"]

    def test_summary_truncated_to_2000_chars(self, tmp_path):
        _write_config(tmp_path)
        snap = _fresh_snap()
        long_summary = "x" * 5000
        packet = build_transfer_packet(
            tmp_path,
            source_runtime="claude",
            snapshot=snap,
            handoff_prep={"directive_summary": long_summary},
        )
        assert len(packet["summary"]) <= 2000


# ---------------------------------------------------------------------------
# transfer_packet.py — write_successor_prompt
# ---------------------------------------------------------------------------


class TestWriteSuccessorPrompt:
    def test_creates_file(self, tmp_path):
        snap = _fresh_snap()
        packet = {
            "transfer_id": str(uuid.uuid4()),
            "budget": {"decision": "spawn"},
            "objective": "Fix bugs",
            "summary": "Did stuff",
            "next_action": "bd ready",
            "risks": ["Risk A"],
            "blockers": [],
            "boot_commands": ["bd ready"],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="handoffs/foo.md")
        assert path.is_file()

    def test_prompt_contains_transfer_id(self, tmp_path):
        tid = str(uuid.uuid4())
        packet = {
            "transfer_id": tid,
            "budget": {"decision": "handoff_only"},
            "objective": "Goal",
            "summary": "",
            "next_action": "bd ready",
            "risks": [],
            "blockers": [],
            "boot_commands": [],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="")
        content = path.read_text(encoding="utf-8")
        assert tid in content

    def test_prompt_contains_budget_decision(self, tmp_path):
        packet = {
            "transfer_id": "id-1",
            "budget": {"decision": "halt_human"},
            "objective": "Goal",
            "summary": "",
            "next_action": "bd ready",
            "risks": [],
            "blockers": [],
            "boot_commands": [],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="")
        content = path.read_text(encoding="utf-8")
        assert "halt_human" in content

    def test_prompt_contains_risks(self, tmp_path):
        packet = {
            "transfer_id": "id-1",
            "budget": {"decision": "spawn"},
            "objective": "Goal",
            "summary": "",
            "next_action": "bd ready",
            "risks": ["Risk alpha", "Risk beta"],
            "blockers": [],
            "boot_commands": [],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="")
        content = path.read_text(encoding="utf-8")
        assert "Risk alpha" in content

    def test_prompt_contains_blockers_section_when_present(self, tmp_path):
        packet = {
            "transfer_id": "id-1",
            "budget": {"decision": "spawn"},
            "objective": "Goal",
            "summary": "",
            "next_action": "bd ready",
            "risks": [],
            "blockers": ["Blocker X"],
            "boot_commands": [],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="")
        content = path.read_text(encoding="utf-8")
        assert "Blocker X" in content

    def test_prompt_summary_truncated_to_3000(self, tmp_path):
        long_summary = "y" * 5000
        packet = {
            "transfer_id": "id-1",
            "budget": {"decision": "spawn"},
            "objective": "Goal",
            "summary": long_summary,
            "next_action": "bd ready",
            "risks": [],
            "blockers": [],
            "boot_commands": [],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="")
        content = path.read_text(encoding="utf-8")
        assert "y" * 3001 not in content

    def test_prompt_contains_boot_commands(self, tmp_path):
        packet = {
            "transfer_id": "id-1",
            "budget": {"decision": "spawn"},
            "objective": "Goal",
            "summary": "",
            "next_action": "bd ready",
            "risks": [],
            "blockers": [],
            "boot_commands": ["bd ready", "python setup.py"],
        }
        path = write_successor_prompt(tmp_path, packet=packet, handoff_path="")
        content = path.read_text(encoding="utf-8")
        assert "bd ready" in content
        assert "python setup.py" in content


# ---------------------------------------------------------------------------
# transfer_packet.py — write_transfer_artifacts
# ---------------------------------------------------------------------------


class TestWriteTransferArtifacts:
    def _make_packet(self, tmp_path: Path) -> dict:
        snap = _fresh_snap()
        return {
            "transfer_id": str(uuid.uuid4()),
            "updated_at": "2026-06-03T00:00:00Z",
            "source_runtime": "claude",
            "objective": "Test",
            "decision": "review",
            "summary": "Summary",
            "risks": [],
            "blockers": [],
            "next_action": "bd ready",
            "confidence": 70,
            "budget_used": {"tool_calls": 0, "files_read": 0, "approx_tokens": 0},
            "successor": {"runtime": "cursor", "spawn_mode": "manual", "model_hint": "", "prompt_path": ""},
            "budget": snap.to_budget_dict(),
            "beads_ready": [],
            "boot_commands": ["bd ready"],
            "forbidden": ["full_transcript"],
            "handoff_path": "",
            "latest_pointer": ".agents/handoffs/latest.json",
        }

    def test_creates_packet_json(self, tmp_path):
        packet = self._make_packet(tmp_path)
        packet_path, _ = write_transfer_artifacts(tmp_path, packet)
        assert packet_path.is_file()

    def test_packet_json_valid(self, tmp_path):
        packet = self._make_packet(tmp_path)
        packet_path, _ = write_transfer_artifacts(tmp_path, packet)
        data = json.loads(packet_path.read_text(encoding="utf-8"))
        assert data["source_runtime"] == "claude"

    def test_creates_successor_prompt(self, tmp_path):
        packet = self._make_packet(tmp_path)
        _, prompt_path = write_transfer_artifacts(tmp_path, packet)
        assert prompt_path.is_file()

    def test_updates_latest_json_when_exists(self, tmp_path):
        handoffs = tmp_path / ".agents" / "handoffs"
        handoffs.mkdir(parents=True)
        latest = handoffs / "latest.json"
        latest.write_text(json.dumps({"some_key": "some_value"}), encoding="utf-8")
        packet = self._make_packet(tmp_path)
        write_transfer_artifacts(tmp_path, packet)
        data = json.loads(latest.read_text(encoding="utf-8"))
        assert "transfer_packet_path" in data
        assert data["transfer_packet_path"] == ".agents/handoffs/transfer_packet.json"

    def test_latest_json_not_required(self, tmp_path):
        # Should not crash if latest.json doesn't exist
        packet = self._make_packet(tmp_path)
        packet_path, prompt_path = write_transfer_artifacts(tmp_path, packet)
        assert packet_path.is_file()
        assert prompt_path.is_file()
