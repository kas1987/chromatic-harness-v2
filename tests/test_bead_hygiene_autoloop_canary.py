"""Regression tests for strict delegation observability canary in autoloop."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.bead_hygiene_autoloop as autoloop


def test_strict_canary_returns_nonzero_on_non_green(monkeypatch, tmp_path: Path) -> None:
    audit_dir = tmp_path / "bead_hygiene"
    delegation_dir = tmp_path / "delegation"
    audit_dir.mkdir(parents=True, exist_ok=True)
    delegation_dir.mkdir(parents=True, exist_ok=True)

    (delegation_dir / "delegation_observability_20260530_000001.json").write_text(
        json.dumps({"status": "yellow"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(autoloop, "AUDIT_DIR", audit_dir)
    monkeypatch.setattr(autoloop, "DELEGATION_AUDIT_DIR", delegation_dir)

    def fake_run_py(script: str, *args: str, timeout: int = 300):
        return {
            "cmd": [script, *args],
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }

    def fake_read_json(path: Path, default):
        text = str(path).replace("\\", "/")
        if text.endswith(".agents/audits/bead_hygiene/latest.json"):
            return {
                "status": "yellow",
                "findings": [
                    {"code": "bead_id_hygiene_warning", "count": 1},
                ],
            }
        if text.endswith(".agents/audits/latest_audit.json"):
            return {"daily_status": "yellow"}
        return default

    monkeypatch.setattr(autoloop, "_run_py", fake_run_py)
    monkeypatch.setattr(autoloop, "_read_json", fake_read_json)
    monkeypatch.setattr(
        autoloop,
        "_delegate_to_claude",
        lambda task, bead_id, spawn, run_id, task_id: {
            "cmd": ["delegate", bead_id, run_id, task_id],
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        },
    )

    monkeypatch.setattr(
        autoloop.sys,
        "argv",
        [
            "bead_hygiene_autoloop.py",
            "--cycles",
            "1",
            "--delegate-claude",
            "--owner-bead-id",
            "chromatic-harness-v2-4n4",
        ],
    )

    rc = autoloop.main()
    assert rc == 2
