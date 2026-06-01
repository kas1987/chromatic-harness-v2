"""Tests for bead_collision_gate.py — network-free, subprocess-mocked."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _lm():
    return _load("lease_manager", "scripts/lease_manager.py")


def _seed_lease(ledger: Path, resource: str, mode: str = "write", agent: str = "AgentA") -> None:
    lm = _lm()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    import uuid

    record = {
        "lease_id": f"lease-{uuid.uuid4().hex[:8]}",
        "task_id": "T-test",
        "owner_agent": agent,
        "resources": [resource],
        "mode": mode,
        "risk_tier": "T2",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": future,
        "heartbeat_at": "2026-01-01T00:00:00Z",
        "rollback_plan": "none",
        "metadata": {},
    }
    records = lm.load_ledger(ledger)
    records.append(record)
    lm.write_ledger(ledger, records)


# ---------------------------------------------------------------------------
# _bd helper — fail-open on subprocess error
# ---------------------------------------------------------------------------


def test_bd_fail_open_on_exception():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    with patch("subprocess.run", side_effect=Exception("bd not found")):
        rc, out = mod._bd("list")
    assert rc == -1
    assert out == ""


# ---------------------------------------------------------------------------
# _get_in_progress_beads
# ---------------------------------------------------------------------------


def test_get_in_progress_beads_parses_list():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    payload = json.dumps(
        [
            {"id": "proj-abc1", "title": "Work item", "owner": "claude"},
        ]
    )
    mock_result = MagicMock(returncode=0, stdout=payload)
    with patch("subprocess.run", return_value=mock_result):
        beads = mod._get_in_progress_beads()
    assert len(beads) == 1
    assert beads[0]["id"] == "proj-abc1"


def test_get_in_progress_beads_empty_on_bad_json():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mock_result = MagicMock(returncode=0, stdout="not-json")
    with patch("subprocess.run", return_value=mock_result):
        beads = mod._get_in_progress_beads()
    assert beads == []


def test_get_in_progress_beads_empty_on_nonzero_exit():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mock_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=mock_result):
        beads = mod._get_in_progress_beads()
    assert beads == []


# ---------------------------------------------------------------------------
# _branch_for_bead
# ---------------------------------------------------------------------------


def test_branch_for_bead_found():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "bd":
            return MagicMock(returncode=0, stdout=json.dumps({"id": "proj-abc1", "title": "t"}))
        # git branch --list
        return MagicMock(returncode=0, stdout="  clean/abc1-my-feature\n")

    with patch("subprocess.run", side_effect=fake_run):
        branch = mod._branch_for_bead("proj-abc1")
    assert branch == "clean/abc1-my-feature"


def test_branch_for_bead_none_when_bead_missing():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mock_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=mock_result):
        branch = mod._branch_for_bead("proj-missing")
    assert branch is None


# ---------------------------------------------------------------------------
# _files_touched_by_branch
# ---------------------------------------------------------------------------


def test_files_touched_by_branch_returns_list():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")

    def fake_run(cmd, **kwargs):
        if "diff" in cmd:
            return MagicMock(returncode=0, stdout="scripts/a.py\nscripts/b.py\n")
        return MagicMock(returncode=1, stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        files = mod._files_touched_by_branch("feature-x")
    assert "scripts/a.py" in files
    assert "scripts/b.py" in files


def test_files_touched_by_branch_empty_on_failure():
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
        files = mod._files_touched_by_branch("missing-branch")
    assert files == []


# ---------------------------------------------------------------------------
# check_files — lease + bead conflict detection
# ---------------------------------------------------------------------------


def test_check_files_safe_no_leases_no_beads(tmp_path, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mod._lm.DEFAULT_LEDGER = ledger

    no_beads = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=no_beads):
        result = mod.check_files(["scripts/foo.py"])

    assert result["status"] == "safe"
    assert result["lease_conflicts"] == []
    assert result["bead_conflicts"] == []


def test_check_files_blocked_by_lease(tmp_path, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="write", agent="OtherAgent")

    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mod._lm.DEFAULT_LEDGER = ledger
    mod._fcg.DEFAULT_LEDGER = ledger

    no_beads = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=no_beads):
        result = mod.check_files(["scripts/foo.py"])

    assert result["status"] == "blocked"
    assert len(result["lease_conflicts"]) >= 1


# ---------------------------------------------------------------------------
# full_status — cross-check with no conflicts
# ---------------------------------------------------------------------------


def test_full_status_ok_when_empty(tmp_path, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mod._lm.DEFAULT_LEDGER = ledger

    no_beads = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=no_beads):
        result = mod.full_status()

    assert result["status"] == "ok"
    assert result["in_progress_beads"] == 0
    assert result["active_write_leases"] == 0
    assert result["bead_lease_conflicts"] == []


# ---------------------------------------------------------------------------
# main — check-bead returns advisory when bd unavailable
# ---------------------------------------------------------------------------


def test_main_check_bead_advisory_on_missing_bd(capsys):
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
        with patch("sys.argv", ["bead_collision_gate.py", "check-bead", "proj-xyz"]):
            rc = mod.main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] in ("advisory", "safe")
    assert rc == 0


# ---------------------------------------------------------------------------
# main — status --json outputs valid JSON
# ---------------------------------------------------------------------------


def test_main_status_json(tmp_path, capsys, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    mod = _load("bead_collision_gate", "scripts/bead_collision_gate.py")
    mod._lm.DEFAULT_LEDGER = ledger

    no_beads = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=no_beads):
        with patch("sys.argv", ["bead_collision_gate.py", "status", "--json"]):
            rc = mod.main()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "status" in data
    assert "bead_lease_conflicts" in data
    assert rc == 0
