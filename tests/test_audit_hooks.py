"""Tests for hook audit script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_audit_hooks_builds_report():
    sys.path.insert(0, str(REPO / "scripts"))
    from audit_hooks import build_report  # noqa: E402

    report = build_report()
    assert "hook_registry" in report
    assert "findings" in report
    assert any(
        r.get("platform") == "cursor"
        for r in report["hook_registry"]
        if r.get("event") == "sessionStart"
    )


def test_project_claude_settings_single_agent_gate():
    path = REPO / ".claude" / "settings.json"
    import json

    doc = json.loads(path.read_text(encoding="utf-8"))
    agent_blocks = 0
    for block in doc.get("hooks", {}).get("PreToolUse", []):
        if block.get("matcher") == "Agent":
            agent_blocks += 1
            for h in block.get("hooks", []):
                assert h.get("timeout"), "Agent gate hook must have timeout"
    assert agent_blocks == 1


def test_audit_hooks_cli_json():
    r = subprocess.run(
        [sys.executable, "scripts/audit_hooks.py", "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "hook_registry" in data
