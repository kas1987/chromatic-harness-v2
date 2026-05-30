from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_log_learning_usage_writes_event(tmp_path, monkeypatch):
    log_path = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    env = os.environ.copy()
    env["CHROMATIC_LEARNING_USAGE_LOG"] = str(log_path)

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "log_learning_usage.py"),
            "--name",
            "Rollback Guard",
            "--event-type",
            "applied_success",
            "--rig-id",
            ".",
            "--learning-path",
            "07_LOGS_AND_AUDIT\\learning_tiers\\latest.md",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert log_path.is_file()
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "applied_success"
    assert event["learning_name"] == "Rollback Guard"
    assert "rig_id" not in event
    assert event["learning_path"] == "07_LOGS_AND_AUDIT/learning_tiers/latest.md"
