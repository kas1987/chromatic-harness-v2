"""Tests for sample-aware lock timeout severity in daily harness audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import daily_harness_audit as dha


def test_low_sample_timeout_rate_downgrades_to_p2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "lock_metrics_rollup.py").write_text(
        "# stub\n", encoding="utf-8"
    )

    # Keep audit focused on lock-threshold behavior.
    monkeypatch.setattr(dha, "CORE_FILES", [])
    monkeypatch.setattr(dha, "CORE_SCRIPTS", [])
    monkeypatch.setattr(dha, "OPTIONAL_COMMANDS", [])

    lock_rollup = {
        "timeout_rate": 0.9,
        "wait_ms": {"p95": 100},
        "event_counts": {"total": 3},
    }

    def fake_run_cmd(_root: Path, cmd: list[str], timeout: int = 45):
        if cmd and "lock_metrics_rollup.py" in str(cmd[1]):
            return {
                "cmd": cmd,
                "returncode": 0,
                "stdout": json.dumps(lock_rollup),
                "stderr": "",
                "ok": True,
            }
        return {"cmd": cmd, "returncode": 0, "stdout": "", "stderr": "", "ok": True}

    monkeypatch.setattr(dha, "run_cmd", fake_run_cmd)

    result = dha.audit(
        root,
        lock_timeout_rate_threshold=0.05,
        lock_wait_p95_threshold_ms=500,
        lock_min_sample_size=20,
    )

    findings = result.get("findings", [])
    hit = [f for f in findings if f.get("code") == "lock_timeout_rate_high_low_sample"]
    assert hit, findings
    assert hit[0].get("severity") == "P2"
