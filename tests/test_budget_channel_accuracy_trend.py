from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_module(repo_root: Path):
    path = repo_root / "scripts" / "budget_channel_accuracy_trend.py"
    spec = importlib.util.spec_from_file_location("budget_channel_accuracy_trend", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_trend_reads_history(tmp_path: Path, monkeypatch):
    budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
    budget_dir.mkdir(parents=True)
    history = budget_dir / "forecast_accuracy_history.jsonl"
    rows = [
        {
            "generated_at": "2026-05-29T00:00:00+00:00",
            "channels": {"vscode": {"week": {"samples": 3, "mape_pct": 20.0}}},
        },
        {
            "generated_at": "2026-05-30T00:00:00+00:00",
            "channels": {"vscode": {"week": {"samples": 3, "mape_pct": 28.0}}},
        },
    ]
    with history.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)
    monkeypatch.setattr(mod, "BUDGET_DIR", budget_dir)
    monkeypatch.setattr(mod, "HISTORY", history)

    payload = mod.build_trend(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    assert payload["coverage"]["history_rows"] == 2
    assert payload["channels"]["vscode"]["points"] == 2
    assert payload["channels"]["vscode"]["week_mape_latest"] == 28.0


def test_build_trend_empty(tmp_path: Path, monkeypatch):
    budget_dir = tmp_path / "07_LOGS_AND_AUDIT" / "budget"
    budget_dir.mkdir(parents=True)
    history = budget_dir / "forecast_accuracy_history.jsonl"
    history.write_text("", encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    mod = _load_module(repo_root)
    monkeypatch.setattr(mod, "REPO", tmp_path)
    monkeypatch.setattr(mod, "BUDGET_DIR", budget_dir)
    monkeypatch.setattr(mod, "HISTORY", history)

    payload = mod.build_trend(datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc))
    assert payload["coverage"]["history_rows"] == 0
    assert payload["status"] == "green"