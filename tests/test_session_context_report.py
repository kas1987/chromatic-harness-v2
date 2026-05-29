"""Tests for session_context_report.py."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "session_context_report.py"
FIXTURE = REPO / "tests" / "fixtures" / "mcp_minimal"
LOG_FILE = REPO / ".agents" / "logs" / "session-context.jsonl"


def test_report_json_fixture():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mcps-path",
            str(FIXTURE),
            "--json",
            "--invoked-by",
            "harness",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "cursor" in data
    assert "claude" in data
    assert "harness" in data
    assert data["summary"]["mcp_tokens_if_enabled"] < 5000
    assert data["invoked_by"] == "harness"


def test_report_log_append(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "session-context.jsonl"
    scripts = str(REPO / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import session_context_report as scr  # noqa: E402

    monkeypatch.setattr(scr, "LOG_DIR", log_dir)
    monkeypatch.setattr(scr, "LOG_FILE", log_file)

    report = scr.build_report(
        invoked_by="cursor",
        mcps_path=FIXTURE,
        profile_name="harness_dev",
    )
    scr.append_log(report)
    assert log_file.is_file()
    line = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert line["invoked_by"] == "cursor"
    assert "warnings" in line
