from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def _load_module(repo_root: Path):
    path = repo_root / "scripts" / "budget_forecast_snapshot.py"
    spec = importlib.util.spec_from_file_location("budget_forecast_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_snapshot_has_forecast_risk_and_provider_breakdown(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence").mkdir(parents=True)

    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n  session_tokens: 200000\n  daily_usd: 25\n  weekly_usd: 100\n  monthly_usd: 400\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json").write_text(
        '{"mcp_audit": {"estimated_tokens_if_enabled": 1500}}\n',
        encoding="utf-8",
    )

    daily = tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl"
    daily.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-05-30T00:00:00+00:00","amount_usd":10.0,"source":"vscode"}',
                '{"timestamp":"2026-05-29T00:00:00+00:00","amount_usd":20.0,"source":"cursor"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json").write_text(
        '{"provider_model_rollup":{"providers":{"workflow":{"events":3,"success":2},"openai":{"events":1,"success":1}},"models":{"workflow:default":{"events":3,"success":2}}}}\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)

    snapshot = mod.build_snapshot(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))

    assert snapshot["boot"]["estimated_tokens"] == 1500
    assert snapshot["forecast"]["risk_level"] in {"green", "yellow", "red"}
    assert "daily_utilization_forecast" in snapshot["forecast"]
    assert "weekly_trend_pct" in snapshot["burn"]
    assert "forecast_remaining_usd" in snapshot["limits"]["weekly"]
    assert "forecast_gap_to_target_usd" in snapshot["limits"]["weekly"]
    assert "target_utilization_pct" in snapshot["limits"]["weekly"]
    assert snapshot["limits"]["weekly"]["target_90_pct_usd"] == 90.0
    assert "daily_spend_needed_to_hit_90_pct_usd" in snapshot["limits"]["weekly"]
    assert snapshot["limits"]["weekly"]["daily_spend_needed_to_hit_90_pct_usd"] >= 0.0

    breakdown = snapshot["model_usage"]["provider_burn_breakdown"]
    assert len(breakdown) >= 1
    assert breakdown[0]["provider"] == "workflow"
    assert breakdown[0]["event_share"] >= breakdown[-1]["event_share"]
    assert snapshot["model_usage"]["unknown_usage"]["warning"] is False
    assert snapshot["channels"]["vscode"]["daily_spent_usd"] == 10.0
    assert snapshot["channels"]["cursor"]["weekly_spent_usd"] == 20.0
    assert "other" in snapshot["channels"]


def test_build_snapshot_marks_red_when_projection_exceeds_cap(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence").mkdir(parents=True)

    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n  session_tokens: 200000\n  daily_usd: 5\n  weekly_usd: 20\n  monthly_usd: 100\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json").write_text(
        '{"mcp_audit": {"estimated_tokens_if_enabled": 1000}}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl").write_text(
        '{"timestamp":"2026-05-30T00:00:00+00:00","amount_usd":30.0}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json").write_text(
        '{"provider_model_rollup":{"providers":{"workflow":{"events":2,"success":1}},"models":{"workflow:default":{"events":2,"success":1}}}}\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)

    snapshot = mod.build_snapshot(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    assert snapshot["forecast"]["daily_over_cap"] is True
    assert snapshot["forecast"]["risk_level"] == "red"
    assert snapshot["limits"]["weekly"]["optimization_state"] in {
        "below_target",
        "at_or_above_target",
    }


def test_unknown_usage_warning_when_unknown_dominates(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence").mkdir(parents=True)

    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n  session_tokens: 200000\n  daily_usd: 25\n  weekly_usd: 100\n  monthly_usd: 400\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json").write_text(
        '{"mcp_audit": {"estimated_tokens_if_enabled": 1000}}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl").write_text(
        '{"timestamp":"2026-05-30T00:00:00+00:00","amount_usd":1.0}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json").write_text(
        '{"provider_model_rollup":{"providers":{"unknown":{"events":60,"success":20},"workflow":{"events":10,"success":7}},"models":{"unknown":{"events":60,"success":20}}}}\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)

    snapshot = mod.build_snapshot(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    unknown_usage = snapshot["model_usage"]["unknown_usage"]
    assert unknown_usage["total_events"] == 70
    assert unknown_usage["unknown_events"] == 60
    assert unknown_usage["warning"] is True


def test_weekly_gap_to_90_is_zero_when_forecast_already_above_target(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence").mkdir(parents=True)

    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n  session_tokens: 200000\n  daily_usd: 25\n  weekly_usd: 100\n  monthly_usd: 400\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json").write_text(
        '{"mcp_audit": {"estimated_tokens_if_enabled": 1000}}\n',
        encoding="utf-8",
    )

    # Heavy weekly burn so projection is above 90% target.
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl").write_text(
        "\n".join(
            [
                '{"timestamp":"2026-05-30T00:00:00+00:00","amount_usd":25.0}',
                '{"timestamp":"2026-05-29T00:00:00+00:00","amount_usd":25.0}',
                '{"timestamp":"2026-05-28T00:00:00+00:00","amount_usd":25.0}',
                '{"timestamp":"2026-05-27T00:00:00+00:00","amount_usd":25.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json").write_text(
        '{"provider_model_rollup":{"providers":{"workflow":{"events":4,"success":4}},"models":{"workflow:default":{"events":4,"success":4}}}}\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)

    snapshot = mod.build_snapshot(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    weekly = snapshot["limits"]["weekly"]
    assert weekly["forecast_gap_to_target_usd"] == 0.0
    assert weekly["optimization_state"] == "at_or_above_target"


def test_dynamic_target_deterministic_lowering(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence").mkdir(parents=True)

    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n"
        "  session_tokens: 200000\n"
        "  daily_usd: 25\n"
        "  weekly_usd: 100\n"
        "  monthly_usd: 400\n"
        "optimization:\n"
        "  weekly_target_utilization_pct_default: 90\n"
        "  weekly_target_utilization_pct_min: 70\n"
        "  weekly_target_utilization_pct_max: 95\n"
        "  lower_target_when_unknown_usage_warning_pct: 15\n"
        "  lower_target_when_risk_red_pct: 5\n"
        "  lower_target_when_risk_yellow_pct: 2\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json").write_text(
        '{"mcp_audit": {"estimated_tokens_if_enabled": 1000}}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl").write_text(
        '{"timestamp":"2026-05-30T00:00:00+00:00","amount_usd":1.0}\n',
        encoding="utf-8",
    )
    # Unknown warning (>=50 events and >=50% unknown) triggers deterministic lowering.
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json").write_text(
        '{"provider_model_rollup":{"providers":{"unknown":{"events":80,"success":20},"workflow":{"events":20,"success":10}},"models":{"unknown":{"events":80,"success":20}}}}\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)

    snapshot = mod.build_snapshot(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    weekly = snapshot["limits"]["weekly"]
    assert weekly["target_utilization_pct"] == 75.0
    assert weekly["target_utilization_usd"] == 75.0
    reasons = (weekly.get("target_policy") or {}).get("reasons") or []
    assert any("unknown_warning" in r for r in reasons)


def test_channel_caps_and_risk_are_applied(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget").mkdir(parents=True)
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence").mkdir(parents=True)

    (tmp_path / "config" / "agent_budget.yaml").write_text(
        "caps:\n"
        "  session_tokens: 200000\n"
        "  daily_usd: 25\n"
        "  weekly_usd: 100\n"
        "  monthly_usd: 400\n"
        "channel_caps:\n"
        "  vscode:\n"
        "    daily_usd: 5\n"
        "    weekly_usd: 10\n"
        "    monthly_usd: 40\n",
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json").write_text(
        '{"mcp_audit": {"estimated_tokens_if_enabled": 500}}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl").write_text(
        '{"timestamp":"2026-05-30T00:00:00+00:00","amount_usd":8.0,"source":"vscode"}\n',
        encoding="utf-8",
    )
    (tmp_path / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json").write_text(
        '{"provider_model_rollup":{"providers":{"workflow":{"events":1,"success":1}},"models":{"workflow:default":{"events":1,"success":1}}}}\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)

    snapshot = mod.build_snapshot(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    ch = snapshot["channels"]["vscode"]
    assert ch["cap_weekly_usd"] == 10.0
    assert ch["risk_level"] in {"yellow", "red"}
    assert "forecast_gap_to_target_usd" in ch
