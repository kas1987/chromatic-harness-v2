"""Claude Code Harness production settings and validation."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_claude_settings_session_lifecycle():
    path = REPO / ".claude" / "settings.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    hooks = doc.get("hooks", {})

    start_cmds = []
    for block in hooks.get("SessionStart", []):
        for h in block.get("hooks", []):
            start_cmds.append(h.get("command", ""))
    assert any("session_start.py" in c for c in start_cmds)

    end_cmds = []
    for block in hooks.get("SessionEnd", []):
        for h in block.get("hooks", []):
            end_cmds.append(h.get("command", ""))
    assert any("session_closeout.py" in c and "claude_code" in c for c in end_cmds)


def test_validate_claude_harness_repo_only_passes():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "scripts/validate_claude_harness.py", "--repo-only"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr or r.stdout


def test_audit_ide_parity_claude_session_end():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "scripts/audit_ide_parity.py", "--root", str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    data = json.loads(r.stdout)
    codes = {f.get("code") for f in data.get("findings", [])}
    assert "claude_session_end_missing" not in codes
