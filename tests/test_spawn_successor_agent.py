"""Tests for spawn_successor_agent exit codes (t7mq: non-manual adapters must return 1 on failure)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import spawn_successor_agent as ssa  # noqa: E402


def _make_packet(tmp_path: Path, decision: str = "spawn", runtime: str = "cursor") -> Path:
    packet = {
        "budget": {"decision": decision},
        "successor": {"runtime": runtime},
        "handoff_path": str(tmp_path / "handoff.md"),
    }
    p = tmp_path / "transfer_packet.json"
    p.write_text(json.dumps(packet))
    return p


def test_cursor_sdk_success_returns_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ssa,
        "load_agent_budget_config",
        lambda _: {"runtimes": {"cursor": {"spawn_adapter": "cursor_sdk"}}},
    )
    monkeypatch.setattr(ssa, "spawn_cursor_sdk", lambda _prompt: (True, "launched"))
    packet = _make_packet(tmp_path, decision="spawn", runtime="cursor")
    monkeypatch.setattr(sys, "argv", ["spawn_successor_agent.py", "--packet", str(packet)])
    code = ssa.main()
    assert code == 0


def test_cursor_sdk_failure_returns_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ssa,
        "load_agent_budget_config",
        lambda _: {"runtimes": {"cursor": {"spawn_adapter": "cursor_sdk"}}},
    )
    monkeypatch.setattr(ssa, "spawn_cursor_sdk", lambda _prompt: (False, "cursor not running"))
    monkeypatch.setattr(ssa, "spawn_manual_bead", lambda _msg: (True, "manual bead created"))
    packet = _make_packet(tmp_path, decision="spawn", runtime="cursor")
    monkeypatch.setattr(sys, "argv", ["spawn_successor_agent.py", "--packet", str(packet)])
    code = ssa.main()
    assert code == 1


def test_claude_cli_success_returns_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ssa,
        "load_agent_budget_config",
        lambda _: {"runtimes": {"claude": {"spawn_adapter": "claude_cli"}}},
    )
    monkeypatch.setattr(ssa, "spawn_claude_cli", lambda _repo, _prompt: (True, "claude launched"))
    packet = _make_packet(tmp_path, decision="spawn", runtime="claude")
    monkeypatch.setattr(sys, "argv", ["spawn_successor_agent.py", "--packet", str(packet)])
    code = ssa.main()
    assert code == 0


def test_claude_cli_failure_returns_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ssa,
        "load_agent_budget_config",
        lambda _: {"runtimes": {"claude": {"spawn_adapter": "claude_cli"}}},
    )
    monkeypatch.setattr(ssa, "spawn_claude_cli", lambda _repo, _prompt: (False, "not installed"))
    monkeypatch.setattr(ssa, "spawn_manual_bead", lambda _msg: (True, "manual bead created"))
    packet = _make_packet(tmp_path, decision="spawn", runtime="claude")
    monkeypatch.setattr(sys, "argv", ["spawn_successor_agent.py", "--packet", str(packet)])
    code = ssa.main()
    assert code == 1


def test_missing_packet_returns_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["spawn_successor_agent.py", "--packet", str(tmp_path / "missing.json")],
    )
    code = ssa.main()
    assert code == 1


def test_decision_not_spawn_returns_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ssa, "spawn_manual_bead", lambda _msg: (True, "manual bead created"))
    packet = _make_packet(tmp_path, decision="handoff_only")
    monkeypatch.setattr(sys, "argv", ["spawn_successor_agent.py", "--packet", str(packet)])
    code = ssa.main()
    assert code == 0
