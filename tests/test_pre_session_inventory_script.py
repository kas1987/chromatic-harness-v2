"""Tests for generate_pre_session_inventory.py."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "generate_pre_session_inventory.py"
FIXTURE_MCPS = REPO / "tests" / "fixtures" / "mcp_minimal"


def test_generate_inventory_with_fixture():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mcps-path",
            str(FIXTURE_MCPS),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    snapshot_path = REPO / "config" / "pre_session" / "inventory.snapshot.json"
    assert snapshot_path.exists()
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert data["summary"]["mcp_server_count"] == 1
    assert data["summary"]["mcp_tool_count"] == 1
    assert (REPO / "docs" / "PRE_SESSION_AND_TOOLS.md").exists()
    assert (REPO / "12_HANDOFFS" / "PRE_SESSION_INVENTORY.md").exists()
