"""Tests for session_status.py — network-free, filesystem-isolated via tmp_path."""

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
# _collect_leases
# ---------------------------------------------------------------------------


def test_collect_leases_empty(tmp_path, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    ledger.write_text("")
    lm = _lm()
    monkeypatch.setattr(lm, "DEFAULT_LEDGER", ledger)

    mod = _load("session_status", "scripts/session_status.py")
    mod._lm.DEFAULT_LEDGER = ledger

    leases = mod._collect_leases()
    assert leases == []


def test_collect_leases_active(tmp_path, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="write", agent="TestAgent")

    mod = _load("session_status", "scripts/session_status.py")
    mod._lm.DEFAULT_LEDGER = ledger

    leases = mod._collect_leases()
    assert len(leases) == 1
    assert leases[0]["owner"] == "TestAgent"
    assert leases[0]["mode"] == "write"
    assert "scripts/foo.py" in leases[0]["resources"]


def test_collect_leases_expired_excluded(tmp_path, monkeypatch):
    lm = _lm()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    import uuid

    expired = {
        "lease_id": f"lease-{uuid.uuid4().hex[:8]}",
        "task_id": "T-old",
        "owner_agent": "OldAgent",
        "resources": ["scripts/old.py"],
        "mode": "write",
        "risk_tier": "T1",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": past,
        "heartbeat_at": "2026-01-01T00:00:00Z",
        "rollback_plan": "none",
        "metadata": {},
    }
    ledger = tmp_path / "active_leases.jsonl"
    lm.write_ledger(ledger, [expired])

    mod = _load("session_status", "scripts/session_status.py")
    mod._lm.DEFAULT_LEDGER = ledger

    leases = mod._collect_leases()
    assert leases == []


# ---------------------------------------------------------------------------
# _detect_conflicts
# ---------------------------------------------------------------------------


def test_detect_conflicts_no_overlap(tmp_path):
    mod = _load("session_status", "scripts/session_status.py")
    leases = [
        {"owner": "A", "mode": "write", "resources": ["scripts/a.py"]},
        {"owner": "B", "mode": "write", "resources": ["scripts/b.py"]},
    ]
    assert mod._detect_conflicts(leases) == []


def test_detect_conflicts_overlap(tmp_path):
    mod = _load("session_status", "scripts/session_status.py")
    leases = [
        {"owner": "A", "mode": "write", "resources": ["scripts/shared.py"]},
        {"owner": "B", "mode": "exclusive", "resources": ["scripts/shared.py"]},
    ]
    conflicts = mod._detect_conflicts(leases)
    assert len(conflicts) == 1
    assert "A" in conflicts[0]
    assert "B" in conflicts[0]


def test_detect_conflicts_read_leases_ignored(tmp_path):
    mod = _load("session_status", "scripts/session_status.py")
    leases = [
        {"owner": "A", "mode": "read", "resources": ["scripts/shared.py"]},
        {"owner": "B", "mode": "read", "resources": ["scripts/shared.py"]},
    ]
    assert mod._detect_conflicts(leases) == []


# ---------------------------------------------------------------------------
# _collect_worktrees (smoke — mocks subprocess)
# ---------------------------------------------------------------------------


def test_collect_worktrees_parses_porcelain():
    mod = _load("session_status", "scripts/session_status.py")
    sample = (
        "worktree /repo/main\nHEAD abc1234567\nbranch refs/heads/main\n\n"
        "worktree /repo/feature\nHEAD def9876543\nbranch refs/heads/feature-x\n"
    )
    mock_result = MagicMock(returncode=0, stdout=sample)
    with patch("subprocess.run", return_value=mock_result):
        wts = mod._collect_worktrees()
    assert len(wts) == 2
    assert wts[0]["branch"] == "main"
    assert wts[1]["branch"] == "feature-x"
    assert wts[0]["head"] == "abc12"


def test_collect_worktrees_empty_on_error():
    mod = _load("session_status", "scripts/session_status.py")
    with patch("subprocess.run", side_effect=Exception("git not found")):
        wts = mod._collect_worktrees()
    assert wts == []


# ---------------------------------------------------------------------------
# _collect_beads (smoke — mocks subprocess)
# ---------------------------------------------------------------------------


def test_collect_beads_parses_json():
    mod = _load("session_status", "scripts/session_status.py")
    beads_json = json.dumps(
        [
            {"id": "proj-abc1", "title": "Fix thing", "owner": "claude"},
            {"id": "proj-abc2", "title": "Add feature", "owner": "cursor"},
        ]
    )
    mock_result = MagicMock(returncode=0, stdout=beads_json)
    with patch("subprocess.run", return_value=mock_result):
        beads = mod._collect_beads()
    assert len(beads) == 2
    assert beads[0]["id"] == "proj-abc1"


def test_collect_beads_empty_on_unavailable():
    mod = _load("session_status", "scripts/session_status.py")
    mock_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=mock_result):
        beads = mod._collect_beads()
    assert beads == []


def test_collect_beads_empty_on_bad_json():
    mod = _load("session_status", "scripts/session_status.py")
    mock_result = MagicMock(returncode=0, stdout="not-json")
    with patch("subprocess.run", return_value=mock_result):
        beads = mod._collect_beads()
    assert beads == []


# ---------------------------------------------------------------------------
# JSON output (integration via main with mocked subprocess)
# ---------------------------------------------------------------------------


def test_main_json_output(tmp_path, capsys, monkeypatch):
    ledger = tmp_path / "active_leases.jsonl"
    mod = _load("session_status", "scripts/session_status.py")
    mod._lm.DEFAULT_LEDGER = ledger

    wt_output = "worktree /repo/main\nHEAD abc1234567\nbranch refs/heads/main\n"
    mock_result = MagicMock(returncode=0, stdout=wt_output)
    # bd list returns empty
    bd_result = MagicMock(returncode=1, stdout="")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git":
            return mock_result
        return bd_result

    with patch("subprocess.run", side_effect=fake_run):
        with patch("sys.argv", ["session_status.py", "--json"]):
            rc = mod.main()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "worktrees" in data
    assert "leases" in data
    assert "conflicts" in data
    assert rc == 0
