"""Tests for the B9 control-plane refresh chain in token_governance_closed_loop.

Asserts the periodic refresh chains all five components end-to-end
(quota_proxy read -> telemetry -> forecast -> controller -> exporter),
is fail-open per step, and surfaces refresh_steps + queue_actions in the
emitted report.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

clp = importlib.import_module("token_governance_closed_loop")


# --- Fakes for the five chained components --------------------------------


class _FakeQuotaState:
    weekly_pct = 72.5
    stale = False
    status = "ok"


def _install_fake_chain(monkeypatch, *, fail: str | None = None):
    """Patch every chained component with a deterministic fake.

    If ``fail`` names a step, that step's fake raises to exercise fail-open.
    """
    calls: list[str] = []

    fake_quota = importlib.import_module("budget.quota_state")
    fake_tel = importlib.import_module("tools.portfolio_token_telemetry")
    fake_fc = importlib.import_module("tools.portfolio_token_forecast")
    fake_ctl = importlib.import_module("control_plane.controller")
    fake_exp = importlib.import_module("dashboards.exporter.token_economy_exporter")

    def _maybe_fail(name: str):
        if fail == name:
            raise RuntimeError(f"boom-{name}")

    def read_quota_state(*a, **k):
        calls.append("quota_proxy_read")
        _maybe_fail("quota_proxy_read")
        return _FakeQuotaState()

    def tel_run(*a, **k):
        calls.append("portfolio_token_telemetry")
        _maybe_fail("portfolio_token_telemetry")
        return {"ledger_path": "x/ledger.jsonl", "rows": 3, "unknown_pct": 0.71}

    def fc_build_report(*a, **k):
        calls.append("portfolio_token_forecast")
        _maybe_fail("portfolio_token_forecast")
        return {"axis_prepaid": {"weekly_quota_pct": 72.5, "status": "red"}}

    class _Decision:
        c_to_t_threshold = 2
        previous_threshold = 3
        direction = -1
        allow_paid_spill = False
        staleness_fallback = False

    def ctl_run_once(*a, **k):
        calls.append("controller")
        _maybe_fail("controller")
        return _Decision()

    def exp_export(*a, **k):
        calls.append("token_economy_exporter")
        _maybe_fail("token_economy_exporter")
        return json.dumps({"chromatic_weekly_quota_pct": 72.5})

    monkeypatch.setattr(fake_quota, "read_quota_state", read_quota_state)
    monkeypatch.setattr(fake_tel, "run", tel_run)
    monkeypatch.setattr(fake_fc, "build_report", fc_build_report)
    monkeypatch.setattr(fake_ctl, "run_once", ctl_run_once)
    monkeypatch.setattr(fake_exp, "export", exp_export)

    return calls


def test_refresh_chain_runs_all_steps_in_order(monkeypatch, tmp_path):
    monkeypatch.setattr(
        importlib.import_module("tools.portfolio_token_forecast"),
        "DEFAULT_OUT",
        tmp_path / "forecast_latest.json",
    )
    calls = _install_fake_chain(monkeypatch)

    steps = clp._refresh_control_plane()

    assert calls == [
        "quota_proxy_read",
        "portfolio_token_telemetry",
        "portfolio_token_forecast",
        "controller",
        "token_economy_exporter",
    ]
    assert [s["name"] for s in steps] == calls
    assert all(s["status"] == "ok" for s in steps)
    # forecast step persisted the extended artifact
    assert (tmp_path / "forecast_latest.json").exists()
    # detail propagated from the fakes
    quota = next(s for s in steps if s["name"] == "quota_proxy_read")
    assert quota["detail"]["weekly_pct"] == 72.5
    ctl = next(s for s in steps if s["name"] == "controller")
    assert ctl["detail"]["c_to_t_threshold"] == 2


def test_refresh_chain_is_fail_open(monkeypatch, tmp_path):
    monkeypatch.setattr(
        importlib.import_module("tools.portfolio_token_forecast"),
        "DEFAULT_OUT",
        tmp_path / "forecast_latest.json",
    )
    calls = _install_fake_chain(monkeypatch, fail="portfolio_token_telemetry")

    steps = clp._refresh_control_plane()

    # All five steps still attempted despite the telemetry failure.
    assert calls == [
        "quota_proxy_read",
        "portfolio_token_telemetry",
        "portfolio_token_forecast",
        "controller",
        "token_economy_exporter",
    ]
    by_name = {s["name"]: s for s in steps}
    assert by_name["portfolio_token_telemetry"]["status"] == "fail"
    assert (
        "boom-portfolio_token_telemetry"
        in by_name["portfolio_token_telemetry"]["error"]
    )
    # Downstream steps still succeed (independent, logged).
    assert by_name["controller"]["status"] == "ok"
    assert by_name["token_economy_exporter"]["status"] == "ok"


def test_main_emits_refresh_steps_and_queue_actions(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        importlib.import_module("tools.portfolio_token_forecast"),
        "DEFAULT_OUT",
        tmp_path / "forecast_latest.json",
    )
    _install_fake_chain(monkeypatch)

    # Mock the four audit checks so main() runs offline and deterministically.
    def _ok(name):
        return clp.CheckResult(name, ["fake"], "pass", 0, "ok", {})

    monkeypatch.setattr(
        clp, "_check_session_context", lambda: _ok("session_context_report")
    )
    monkeypatch.setattr(
        clp, "_check_mcp_audit", lambda profile: _ok("audit_mcp_context")
    )
    monkeypatch.setattr(
        clp,
        "_check_workflow_token_governance",
        lambda: _ok("validate_workflow_token_governance"),
    )
    monkeypatch.setattr(
        clp, "_check_daily_strict", lambda: _ok("daily_harness_audit_strict")
    )

    # Redirect report writes into tmp so the test never touches repo logs.
    written = {}

    def _fake_write(report):
        written["report"] = report
        # main() prints REPO-relative artifact paths, so keep them under REPO.
        p = clp.REPO / "07_LOGS_AND_AUDIT" / "token_governance" / "latest.json"
        return p, p, p

    monkeypatch.setattr(clp, "_write_reports", _fake_write)
    monkeypatch.setattr(sys, "argv", ["token_governance_closed_loop.py"])

    rc = clp.main()
    assert rc == 0

    report = written["report"]
    assert report["status"] == "green"
    assert [s["name"] for s in report["refresh_steps"]] == [
        "quota_proxy_read",
        "portfolio_token_telemetry",
        "portfolio_token_forecast",
        "controller",
        "token_economy_exporter",
    ]
    assert all(s["status"] == "ok" for s in report["refresh_steps"])
    # queue_actions key always present (empty without --enqueue-suggestions).
    assert report["queue_actions"] == []

    out = json.loads(capsys.readouterr().out)
    assert "refresh_steps" in out
