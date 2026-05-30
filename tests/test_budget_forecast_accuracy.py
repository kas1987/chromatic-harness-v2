from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_module(repo_root: Path):
    path = repo_root / "scripts" / "budget_forecast_accuracy.py"
    spec = importlib.util.spec_from_file_location("budget_forecast_accuracy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_accuracy_scores_known_predictions(tmp_path: Path, monkeypatch):
    budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
    budget_dir.mkdir(parents=True)

    forecast_history = [
        {
            "generated_at": "2026-05-28T12:00:00+00:00",
            "forecast": {
                "end_of_day_usd": 10.0,
                "end_of_week_usd": 50.0,
                "end_of_month_usd": 150.0,
            },
            "channels": {
                "vscode": {"end_of_day_usd": 10.0, "end_of_week_usd": 10.0, "end_of_month_usd": 10.0},
                "cursor": {"end_of_day_usd": 0.0, "end_of_week_usd": 0.0, "end_of_month_usd": 0.0},
            },
        },
        {
            "generated_at": "2026-05-29T12:00:00+00:00",
            "forecast": {
                "end_of_day_usd": 20.0,
                "end_of_week_usd": 60.0,
                "end_of_month_usd": 160.0,
            },
            "channels": {
                "vscode": {"end_of_day_usd": 0.0, "end_of_week_usd": 0.0, "end_of_month_usd": 0.0},
                "cursor": {"end_of_day_usd": 20.0, "end_of_week_usd": 20.0, "end_of_month_usd": 20.0},
            },
        },
    ]
    with (budget_dir / "forecast_history.jsonl").open("w", encoding="utf-8") as fh:
        for row in forecast_history:
            fh.write(json.dumps(row) + "\n")

    daily_rows = [
        {"timestamp": "2026-05-28T01:00:00+00:00", "amount_usd": 10.0, "source": "vscode"},
        {"timestamp": "2026-05-29T01:00:00+00:00", "amount_usd": 20.0, "source": "cursor"},
        {"timestamp": "2026-05-30T01:00:00+00:00", "amount_usd": 5.0, "source": "vscode"},
    ]
    with (budget_dir / "daily.jsonl").open("w", encoding="utf-8") as fh:
        for row in daily_rows:
            fh.write(json.dumps(row) + "\n")

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)
    monkeypatch.setattr(mod, "BUDGET_DIR", budget_dir)
    monkeypatch.setattr(mod, "HISTORY", budget_dir / "forecast_history.jsonl")
    monkeypatch.setattr(mod, "DAILY", budget_dir / "daily.jsonl")

    payload = mod.build_accuracy(datetime(2026, 5, 31, 0, 0, 0, tzinfo=timezone.utc))
    assert payload["coverage"]["forecast_rows"] == 2
    assert payload["coverage"]["daily_ledger_rows"] == 3
    assert payload["coverage"]["scored_rows"] == 2
    assert payload["metrics"]["day"]["samples"] == 2
    assert payload["metrics"]["day"]["mae_usd"] >= 0.0
    assert payload["channels"]["vscode"]["day"]["samples"] == 2
    assert payload["channels"]["cursor"]["day"]["samples"] == 2


def test_build_accuracy_handles_empty_inputs(tmp_path: Path, monkeypatch):
    budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
    budget_dir.mkdir(parents=True)
    (budget_dir / "forecast_history.jsonl").write_text("", encoding="utf-8")
    (budget_dir / "daily.jsonl").write_text("", encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)
    monkeypatch.setattr(mod, "BUDGET_DIR", budget_dir)
    monkeypatch.setattr(mod, "HISTORY", budget_dir / "forecast_history.jsonl")
    monkeypatch.setattr(mod, "DAILY", budget_dir / "daily.jsonl")

    payload = mod.build_accuracy(datetime(2026, 5, 31, 0, 0, 0, tzinfo=timezone.utc))
    assert payload["coverage"]["forecast_rows"] == 0
    assert payload["coverage"]["scored_rows"] == 0
    assert payload["metrics"]["week"]["samples"] == 0