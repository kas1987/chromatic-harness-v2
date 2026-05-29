"""Guardrails for lite Claude Code workflows in repo."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".claude/workflows"


def test_lite_workflows_exist():
    for name in ("ship.js", "qa.js", "close-issue.js", "hotfix.js", "go.js"):
        assert (WF / name).is_file(), f"missing {name}"


def test_go_lite_no_crank_or_swarm():
    text = (WF / "go.js").read_text(encoding="utf-8").lower()
    assert "do not run /crank" in text or "no crank" in text
    assert "/swarm" in text
    assert "workflow_go" in text
    assert "label: 'crank" not in text


def test_ship_lite_no_crank_invoke():
    text = (WF / "ship.js").read_text(encoding="utf-8").lower()
    assert "do not run /crank" in text or "no crank" in text
    assert "await agent" in text
    assert "label: 'crank" not in text and 'phase: "crank' not in text


def test_heavy_archive_not_synced_by_script():
    ps1 = (REPO / "scripts/sync_claude_workflows.ps1").read_text(encoding="utf-8")
    assert "HEAVY" in ps1
    assert "*.js" in ps1
