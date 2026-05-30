from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_backfill_learning_usage_writes_events(tmp_path):
    harvest = tmp_path / ".agents" / "harvest" / "latest.json"
    usage = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    harvest.parent.mkdir(parents=True, exist_ok=True)
    harvest.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-30T00:00:00Z",
                "promoted": [
                    {
                        "from": "C:/repo/.agents/learnings/rollback-guard.md",
                        "rig_id": "fusion-computer",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    script = REPO / "scripts" / "backfill_learning_usage.py"
    copied_script = tmp_path / "scripts" / "backfill_learning_usage.py"
    copied_script.parent.mkdir(parents=True, exist_ok=True)
    copied_script.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(copied_script), "--write"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert usage.is_file()
    lines = [ln for ln in usage.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "applied_success"
    assert event["learning_name"] == "rollback-guard"
    assert event["rig_id"] == "fusion-computer"

    proc2 = subprocess.run(
        [sys.executable, str(copied_script), "--write"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc2.returncode == 0
    lines2 = [ln for ln in usage.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines2) == 1
