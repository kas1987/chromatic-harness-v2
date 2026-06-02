"""Tests for the collision awareness surface (OMH-1, scripts/collision_status.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import collision_status  # noqa: E402


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _lease(owner, resources, mode="write", ttl_min=30, age_min=1, status="active", lease_id="L1"):
    now = datetime.now(timezone.utc)
    return {
        "lease_id": lease_id,
        "task_id": f"T-{owner}",
        "owner_agent": owner,
        "resources": resources,
        "mode": mode,
        "status": status,
        "created_at": _iso(now - timedelta(minutes=age_min)),
        "expires_at": _iso(now + timedelta(minutes=ttl_min)),
        "heartbeat_at": _iso(now),
    }


def _write(path: Path, leases):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(l) for l in leases) + "\n", encoding="utf-8")


def test_empty_ledger_is_safe(tmp_path: Path):
    status = collision_status.build_status(tmp_path / "none.jsonl")
    assert status["active_count"] == 0
    assert status["holders"] == [] and status["has_conflicts"] is False
    assert "No active file claims" in collision_status.render_table(status)


def test_lists_active_holders(tmp_path: Path):
    led = tmp_path / "leases.jsonl"
    _write(led, [_lease("Sentinel", ["scripts/a.py"], lease_id="L1")])
    status = collision_status.build_status(led)
    assert status["active_count"] == 1
    h = status["holders"][0]
    assert h["owner_agent"] == "Sentinel" and h["resources"] == ["scripts/a.py"]
    assert h["age_minutes"] is not None and h["expires_in_minutes"] is not None
    assert "Sentinel" in collision_status.render_table(status)


def test_detects_live_conflict_same_file_two_owners(tmp_path: Path):
    led = tmp_path / "leases.jsonl"
    _write(
        led,
        [
            _lease("Sentinel", ["scripts/shared.py"], lease_id="L1"),
            _lease("Auditor", ["scripts/shared.py"], lease_id="L2"),
        ],
    )
    status = collision_status.build_status(led)
    assert status["has_conflicts"] is True
    assert status["conflicts"][0]["resources"] == ["scripts/shared.py"]
    assert "LIVE CONFLICTS" in collision_status.render_table(status)


def test_read_leases_do_not_conflict(tmp_path: Path):
    led = tmp_path / "leases.jsonl"
    _write(
        led,
        [
            _lease("Sentinel", ["scripts/shared.py"], mode="read", lease_id="L1"),
            _lease("Auditor", ["scripts/shared.py"], mode="read", lease_id="L2"),
        ],
    )
    assert collision_status.build_status(led)["has_conflicts"] is False


def test_expired_leases_excluded(tmp_path: Path):
    led = tmp_path / "leases.jsonl"
    _write(led, [_lease("Sentinel", ["scripts/a.py"], ttl_min=-5, lease_id="L1")])
    assert collision_status.build_status(led)["active_count"] == 0


def test_same_owner_no_self_conflict(tmp_path: Path):
    led = tmp_path / "leases.jsonl"
    _write(
        led,
        [
            _lease("Sentinel", ["scripts/a.py"], lease_id="L1"),
            _lease("Sentinel", ["scripts/a.py"], lease_id="L2"),
        ],
    )
    assert collision_status.build_status(led)["has_conflicts"] is False


def test_cli_runs_clean_and_json(tmp_path: Path):
    led = tmp_path / "leases.jsonl"
    _write(led, [_lease("Sentinel", ["scripts/a.py"], lease_id="L1")])
    # default (no ledger) must exit 0 — this is the bead's validation command
    r0 = subprocess.run(
        [sys.executable, str(SCRIPTS / "collision_status.py")], capture_output=True, text=True, cwd=REPO
    )
    assert r0.returncode == 0
    # json mode against our fixture ledger
    r1 = subprocess.run(
        [sys.executable, str(SCRIPTS / "collision_status.py"), "--ledger", str(led), "--json"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert r1.returncode == 0
    assert json.loads(r1.stdout)["active_count"] == 1
