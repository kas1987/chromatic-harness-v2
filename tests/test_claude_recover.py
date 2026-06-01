"""Tests for scripts/claude_recover.py — /recover emergency recovery orchestrator.

Network-free. Lease ledger and log written to tmp_path fixtures.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "claude_recover.py"


def _load(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("claude_recover", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["claude_recover"] = mod
    spec.loader.exec_module(mod)

    # Redirect all file I/O to tmp_path
    monkeypatch.setattr(mod, "RECOVERY_LOG", tmp_path / "recovery_log.jsonl")
    monkeypatch.setattr(mod, "LEASE_LEDGER", tmp_path / "active_leases.jsonl")
    monkeypatch.setattr(mod, "HEALTH_REPORT", tmp_path / "health_latest.json")
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_lease(path: Path, leases: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in leases) + "\n",
        encoding="utf-8",
    )


def _future_ts(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past_ts(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# inspect mode
# ---------------------------------------------------------------------------


class TestInspectMode:
    def test_inspect_no_leases_green(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        result = mod.mode_inspect()
        assert result["mode"] == "inspect"
        assert result["mutation"] is False
        assert result["active_leases"] == 0
        assert result["stale_leases"] == 0

    def test_inspect_counts_active_and_stale(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        leases = [
            {"lease_id": "l1", "status": "active", "expires_at": _future_ts()},
            {"lease_id": "l2", "status": "active", "expires_at": _past_ts()},
            {"lease_id": "l3", "status": "released", "expires_at": _past_ts()},
        ]
        _write_lease(mod.LEASE_LEDGER, leases)
        result = mod.mode_inspect()
        assert result["active_leases"] == 1
        assert result["stale_leases"] == 1
        assert "l2" in result["stale_lease_ids"]
        assert "l1" in result["active_lease_ids"]

    def test_inspect_suggests_stale_lease_action(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_lease(
            mod.LEASE_LEDGER,
            [{"lease_id": "l-stale", "status": "active", "expires_at": _past_ts()}],
        )
        result = mod.mode_inspect()
        assert any("stale" in s.lower() for s in result["suggested_actions"])

    def test_inspect_warns_on_yellow_health(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        mod.HEALTH_REPORT.write_text(json.dumps({"overall_status": "yellow"}), encoding="utf-8")
        result = mod.mode_inspect()
        assert any("yellow" in s for s in result["suggested_actions"])

    def test_inspect_logs_to_recovery_log(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        run_id = mod.make_run_id()
        result = mod.build_result(mod.mode_inspect(), run_id)
        mod.append_log(result)
        lines = mod.RECOVERY_LOG.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        logged = json.loads(lines[0])
        assert logged["run_id"] == run_id
        assert logged["mode"] == "inspect"


# ---------------------------------------------------------------------------
# stale-lease mode
# ---------------------------------------------------------------------------


class TestStaleLease:
    def test_list_only_no_mutation(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_lease(
            mod.LEASE_LEDGER,
            [{"lease_id": "l-stale", "status": "active", "expires_at": _past_ts()}],
        )
        result = mod.mode_stale_lease(lease_id=None, reason=None, list_only=True)
        assert result["action"] == "list"
        assert result["mutation"] is False
        assert len(result["stale_leases"]) == 1

    def test_expire_stale_lease_succeeds(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_lease(
            mod.LEASE_LEDGER,
            [
                {
                    "lease_id": "l-stale",
                    "status": "active",
                    "expires_at": _past_ts(),
                    "owner": "agent-a",
                    "resources": ["scripts/foo.py"],
                }
            ],
        )
        result = mod.mode_stale_lease("l-stale", reason="owner confirmed absent", list_only=False)
        assert result["action"] == "expired"
        assert result["mutation"] is True
        # Verify lease is marked expired on disk
        records = [json.loads(l) for l in mod.LEASE_LEDGER.read_text().splitlines() if l.strip()]
        assert records[0]["status"] == "expired"
        assert records[0]["recovery_reason"] == "owner confirmed absent"

    def test_expire_active_lease_triggers_stop(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_lease(
            mod.LEASE_LEDGER,
            [{"lease_id": "l-live", "status": "active", "expires_at": _future_ts()}],
        )
        result = mod.mode_stale_lease("l-live", reason="forced", list_only=False)
        assert result.get("halt") is True
        assert result["stop_condition"] == "lease_active_owner_present"

    def test_expire_without_reason_triggers_stop(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_lease(
            mod.LEASE_LEDGER,
            [{"lease_id": "l-stale", "status": "active", "expires_at": _past_ts()}],
        )
        result = mod.mode_stale_lease("l-stale", reason=None, list_only=False)
        assert result.get("halt") is True
        assert result["stop_condition"] == "rollback_plan_missing"


# ---------------------------------------------------------------------------
# failed-ship mode
# ---------------------------------------------------------------------------


class TestFailedShip:
    def test_no_run_log_returns_zero_runs(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        # Point run_log to nonexistent file
        run_log = tmp_path / "run_log.jsonl"
        monkeypatch.setattr(
            mod,
            "mode_failed_ship",
            lambda: {
                "mode": "failed_ship",
                "recent_runs": 0,
                "failed_runs": 0,
                "latest_failures": [],
                "mutation": False,
                "next_step": "inspect",
            },
        )
        result = mod.mode_failed_ship()
        assert result["mode"] == "failed_ship"
        assert result["mutation"] is False

    def test_failed_ship_no_mutation_ever(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        result = mod.mode_failed_ship()
        assert result["mutation"] is False


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCli:
    def test_inspect_default_exit_0(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        rc = mod.main(["inspect"])
        assert rc == 0

    def test_stale_lease_list_exit_0(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        rc = mod.main(["stale-lease", "--list"])
        assert rc == 0

    def test_stop_condition_exit_1(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_lease(
            mod.LEASE_LEDGER,
            [{"lease_id": "l-live", "status": "active", "expires_at": _future_ts()}],
        )
        rc = mod.main(["stale-lease", "--lease-id", "l-live", "--reason", "test"])
        assert rc == 1

    def test_default_mode_is_inspect(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        rc = mod.main([])
        assert rc == 0
        lines = mod.RECOVERY_LOG.read_text(encoding="utf-8").strip().splitlines()
        logged = json.loads(lines[0])
        assert logged["mode"] == "inspect"

    def test_output_is_valid_json(self, monkeypatch, tmp_path, capsys):
        mod = _load(monkeypatch, tmp_path)
        mod.main(["inspect"])
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "run_id" in parsed
        assert "timestamp" in parsed

    def test_run_id_prefix(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        run_id = mod.make_run_id()
        assert run_id.startswith("rcv_")
        assert len(run_id) == 12  # "rcv_" + 8 hex chars


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
