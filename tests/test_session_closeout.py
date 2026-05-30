"""Session closeout dry-run and spawn gating."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_session_closeout_dry_run():
    r = subprocess.run(
        [
            sys.executable,
            str(_REPO / "scripts" / "session_closeout.py"),
            "--dry-run",
            "--invoked-by",
            "cli",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "budget" in data
    assert "transfer_packet" in data
    assert data["transfer_packet"]["source_runtime"] == "cli"


def test_spawn_blocked_without_spawn_decision(tmp_path):
    packet = {
        "budget": {"decision": "handoff_only"},
        "successor": {
            "runtime": "cursor",
            "prompt_path": ".agents/handoffs/successor_prompt.md",
        },
        "summary": "test",
        "handoff_path": "12_HANDOFFS/sessions/x.md",
    }
    p = tmp_path / "transfer_packet.json"
    p.write_text(json.dumps(packet), encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            str(_REPO / "scripts" / "spawn_successor_agent.py"),
            "--packet",
            str(p),
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out.get("adapter") == "manual" or out.get("decision") == "handoff_only"


def test_build_transfer_packet():
    sys.path.insert(0, str(_REPO / "02_RUNTIME"))
    from budget.ledger import BudgetSnapshot  # noqa: E402
    from budget.transfer_packet import build_transfer_packet  # noqa: E402

    snap = BudgetSnapshot(session_est_tokens=1000, decision="handoff_only")
    pkt = build_transfer_packet(
        _REPO,
        source_runtime="cursor",
        snapshot=snap,
        handoff_path="12_HANDOFFS/sessions/T.md",
    )
    assert pkt["transfer_id"]
    assert pkt["budget"]["decision"] == "handoff_only"
    assert pkt["successor"]["spawn_mode"] == "manual"
