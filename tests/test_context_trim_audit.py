"""Tests for scripts/context_trim_audit.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO / "scripts" / "context_trim_audit.py"


def test_context_trim_audit_writes_json(tmp_path):
    # Minimal fake repo with one large file pattern
    (tmp_path / "AGENTS.md").write_text("x\n" * 1000, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("Beads Issue Tracker\n" * 2, encoding="utf-8")
    (tmp_path / "AGENT_OPERATIONS.md").write_text(
        "Beads Issue Tracker\n", encoding="utf-8"
    )

    out = tmp_path / ".agents" / "context" / "audit.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--root",
            str(tmp_path),
            "--out",
            ".agents/context/audit.json",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "risk_level" in data
    assert "findings" in data
    assert data["summary"]["total_findings"] >= 1


def test_context_trim_audit_stdlib_only():
    text = AUDIT_SCRIPT.read_text(encoding="utf-8")
    assert "import requests" not in text
    assert "from pathlib import Path" in text
