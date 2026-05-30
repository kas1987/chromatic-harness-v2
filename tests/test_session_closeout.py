"""Session closeout dry-run and spawn gating."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

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
    assert "epic_timestamp_utc" in data
    assert "epic_title" in data
    assert "epic_swot_telemetry_key" in data
    assert "epic_swot_summary" in data
    assert "epic_swot_policy" in data
    assert "closeout_telemetry_path" in data
    assert "closeout_telemetry_history_path" in data
    assert "auto_start_ok" in data
    assert data["epic_swot_telemetry_key"] == ""
    assert data["epic_swot_summary"]["telemetry_key"] == ""
    assert data["epic_swot_policy"]["allow_create"] is False
    assert data["closeout_telemetry_path"] == ""
    assert data["closeout_telemetry_history_path"] == ""
    assert data["auto_start_ok"] is False


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


def test_run_bd_fallback_on_winerror2(monkeypatch):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    calls = []

    def fake_run(cmd, *, timeout=120, cwd=None):
        calls.append(cmd)
        if cmd[:1] == ["bd"]:
            return 1, "[WinError 2] The system cannot find the file specified"
        if cmd[:3] == ["cmd", "/c", "bd"]:
            return 0, "Created issue: chromatic-harness-v2-test"
        return 1, "unexpected"

    monkeypatch.setattr(session_closeout, "_run", fake_run)
    code, out = session_closeout._run_bd(
        ["create", "--type", "epic", "--title", "x"], timeout=30
    )
    assert code == 0
    assert "Created issue" in out
    assert calls[0][0] == "bd"
    assert calls[1][:3] == ["cmd", "/c", "bd"]


def test_run_bd_no_fallback_for_other_errors(monkeypatch):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    calls = []

    def fake_run(cmd, *, timeout=120, cwd=None):
        calls.append(cmd)
        return 1, "permission denied"

    monkeypatch.setattr(session_closeout, "_run", fake_run)
    code, out = session_closeout._run_bd(
        ["create", "--type", "task", "--title", "x"], timeout=30
    )
    assert code == 1
    assert out == "permission denied"
    assert len(calls) == 1


def test_epic_swot_title_has_utc_timestamp(monkeypatch):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    calls = []

    def fake_run_bd(args, *, timeout=60):
        calls.append(args)
        if args[:2] == ["create", "--type"] and "epic" in args:
            return 0, "Created issue: chromatic-harness-v2-epic"
        if args[:2] == ["create", "--type"] and "task" in args:
            return 0, "Created issue: chromatic-harness-v2-task"
        if args[:2] == ["update", "chromatic-harness-v2-task"]:
            return 0, "Updated issue: chromatic-harness-v2-task"
        return 1, "unexpected"

    monkeypatch.setattr(session_closeout, "_run_bd", fake_run_bd)
    data = session_closeout.ensure_epic_swot_chain()

    assert data["ok"] is True
    assert re.fullmatch(r"\d{8}T\d{6}Z", data["timestamp_utc"])
    assert re.fullmatch(r"EPIC-SWOT-NEXT-\d{8}T\d{6}Z", data["telemetry_key"])
    assert f"[{data['timestamp_utc']}]" in data["epic_title"]
    assert f"[{data['timestamp_utc']}]" in data["task_title"]

    epic_create = next(
        c for c in calls if c[:2] == ["create", "--type"] and "epic" in c
    )
    epic_title = epic_create[epic_create.index("--title") + 1]
    assert epic_title == data["epic_title"]

    task_create = next(
        c for c in calls if c[:2] == ["create", "--type"] and "task" in c
    )
    task_title = task_create[task_create.index("--title") + 1]
    assert task_title == data["task_title"]


def test_apply_epic_swot_aliases_consistent_mapping():
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    epic = {
        "ok": True,
        "telemetry_key": "EPIC-SWOT-NEXT-20260530T091200Z",
        "timestamp_utc": "20260530T091200Z",
        "epic_title": "EPIC-SWOT NEXT [20260530T091200Z]: Post-Closeout SWOT Seed (2026-05-30)",
        "epic_id": "chromatic-harness-v2-epic",
        "task_id": "chromatic-harness-v2-task",
        "parent_update": {"ok": True},
    }
    result = {}

    session_closeout._apply_epic_swot_aliases(result, epic)

    assert (
        result["epic_swot_telemetry_key"]
        == result["epic_swot_summary"]["telemetry_key"]
    )
    assert result["epic_timestamp_utc"] == result["epic_swot_summary"]["timestamp_utc"]
    assert result["epic_title"] == result["epic_swot_summary"]["epic_title"]
    assert result["epic_swot_summary"]["parent_linked"] is True


def test_apply_epic_swot_aliases_defaults_when_missing():
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    result = {}
    session_closeout._apply_epic_swot_aliases(result, None)

    assert result["epic_swot_telemetry_key"] == ""
    assert result["epic_timestamp_utc"] == ""
    assert result["epic_title"] == ""
    assert result["epic_swot_summary"]["ok"] is False
    assert result["epic_swot_summary"]["parent_linked"] is False


def test_build_closeout_telemetry_snapshot_schema():
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    result = {
        "invoked_by": "vscode",
        "budget": {"decision": "spawn"},
        "epic_swot_telemetry_key": "EPIC-SWOT-NEXT-20260530T091500Z",
        "epic_timestamp_utc": "20260530T091500Z",
        "epic_title": "EPIC-SWOT NEXT [20260530T091500Z]: Post-Closeout SWOT Seed (2026-05-30)",
        "epic_swot_summary": {
            "epic_id": "chromatic-harness-v2-epic",
            "task_id": "chromatic-harness-v2-task",
            "parent_linked": True,
        },
        "epic_swot_policy": {
            "allow_create": True,
            "confidence_score": 0.83,
            "decision_reason": "allow",
        },
        "auto_start_ok": True,
    }

    snap = session_closeout._build_closeout_telemetry_snapshot(result)
    assert snap["invoked_by"] == "vscode"
    assert snap["budget_decision"] == "spawn"
    assert snap["epic_swot_telemetry_key"] == "EPIC-SWOT-NEXT-20260530T091500Z"
    assert snap["epic_timestamp_utc"] == "20260530T091500Z"
    assert snap["epic_id"] == "chromatic-harness-v2-epic"
    assert snap["task_id"] == "chromatic-harness-v2-task"
    assert snap["parent_linked"] is True
    assert snap["epic_policy_allow"] is True
    assert snap["epic_policy_confidence"] == 0.83
    assert snap["epic_policy_reason"] == "allow"
    assert snap["auto_start_ok"] is True


def test_write_closeout_telemetry_snapshot_writes_latest_and_history(
    tmp_path: Path, monkeypatch
):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    monkeypatch.setattr(session_closeout, "_REPO", tmp_path)
    result = {
        "invoked_by": "vscode",
        "budget": {"decision": "spawn"},
        "epic_swot_policy": {"allow_create": True, "confidence_score": 0.8},
        "epic_swot_summary": {"epic_id": "ep-1", "task_id": "task-1"},
    }

    paths = session_closeout._write_closeout_telemetry_snapshot(result)

    latest = tmp_path / paths["latest"]
    history = tmp_path / paths["history"]
    assert latest.is_file()
    assert history.is_file()
    assert latest.read_text(encoding="utf-8") == history.read_text(encoding="utf-8")


def test_main_passes_epic_policy_config_override(tmp_path: Path, monkeypatch):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    cfg = tmp_path / "epic_swot_policy.json"
    cfg.write_text(json.dumps({"confidence_threshold": 0.91}), encoding="utf-8")

    class FakeSnapshot:
        session_est_tokens = 0
        decision = "review"
        reasons: list[str] = []

        def to_budget_dict(self):
            return {"decision": self.decision}

    class FakeLedger:
        def __init__(self, _repo):
            pass

        def snapshot(self):
            return FakeSnapshot()

    captured: dict[str, Path | None] = {}

    def fake_evaluate_epic_swot_policy(**kwargs):
        captured["policy_config_path"] = kwargs.get("policy_config_path")
        return {
            "allow_create": False,
            "confidence_score": 0.0,
            "threshold": 0.55,
            "decision_reason": "blocked",
        }

    monkeypatch.setattr(session_closeout, "BudgetLedger", FakeLedger)
    monkeypatch.setattr(session_closeout, "git_snapshot", lambda: {"status_short": []})
    monkeypatch.setattr(session_closeout, "beads_ready_ids", lambda: [])
    monkeypatch.setattr(
        session_closeout,
        "write_handoff",
        lambda *args, **kwargs: _REPO / "12_HANDOFFS" / "handoff.md",
    )
    monkeypatch.setattr(session_closeout, "build_transfer_packet", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(session_closeout, "write_transfer_artifacts", lambda *args, **kwargs: None)
    monkeypatch.setattr(session_closeout, "log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(session_closeout, "evaluate_epic_swot_policy", fake_evaluate_epic_swot_policy)
    monkeypatch.setattr(session_closeout, "find_latest_open_swot_epic", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        session_closeout,
        "_write_closeout_telemetry_snapshot",
        lambda result: {"latest": "latest.json", "history": "history.json"},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "session_closeout.py",
            "--invoked-by",
            "cli",
            "--epic-policy-config",
            str(cfg),
        ],
    )

    stdout = StringIO()
    with redirect_stdout(stdout):
        rc = session_closeout.main()

    assert rc == 0
    assert captured["policy_config_path"] == cfg


def test_evaluate_epic_swot_policy_blocks_recent_open_epic(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    now = datetime(2026, 5, 30, 9, 20, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-ep1",
                        "title": "EPIC-SWOT NEXT [20260530T091000Z]: Post-Closeout SWOT Seed (2026-05-30)",
                        "issue_type": "epic",
                        "status": "open",
                        "created_at": "2026-05-30T09:10:00Z",
                    }
                )
            ]
        ),
        encoding="utf-8",
    )
    gov = tmp_path / "latest.json"
    gov.write_text(
        json.dumps({"event_count": 900, "canonical_coverage": {"provider": 0.7}}),
        encoding="utf-8",
    )

    snap = SimpleNamespace(session_est_tokens=150000, decision="spawn")
    out = session_closeout.evaluate_epic_swot_policy(
        snapshot=snap,
        beads_ready=["a", "b", "c", "d", "e"],
        git={"status_short": ["M a", "M b", "M c", "M d", "M e", "M f", "M g", "M h"]},
        issues_path=issues,
        governance_path=gov,
        now_utc=now,
    )
    assert out["allow_create"] is False
    assert "recent open EPIC-SWOT" in out["decision_reason"]


def test_evaluate_epic_swot_policy_allows_when_complexity_high_and_no_recent_open(
    tmp_path: Path,
):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    now = datetime(2026, 5, 30, 9, 20, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text(
        json.dumps(
            {
                "id": "chromatic-harness-v2-old",
                "title": "EPIC-SWOT NEXT [20260528T091000Z]: Post-Closeout SWOT Seed (2026-05-28)",
                "issue_type": "epic",
                "status": "closed",
                "created_at": "2026-05-28T09:10:00Z",
            }
        ),
        encoding="utf-8",
    )
    gov = tmp_path / "latest.json"
    gov.write_text(
        json.dumps(
            {
                "event_count": 600,
                "canonical_coverage": {
                    "provider": 0.6,
                    "model": 0.7,
                    "execution_status": 0.8,
                    "task_id": 0.75,
                },
            }
        ),
        encoding="utf-8",
    )

    snap = SimpleNamespace(session_est_tokens=160000, decision="spawn")
    # Patch live query to force JSONL fallback so the test controls exactly which beads exist.
    import unittest.mock

    with unittest.mock.patch.object(
        session_closeout, "_fetch_swot_rows_live", return_value=None
    ):
        out = session_closeout.evaluate_epic_swot_policy(
            snapshot=snap,
            beads_ready=[str(i) for i in range(9)],
            git={"status_short": [f"M f{i}" for i in range(30)]},
            issues_path=issues,
            governance_path=gov,
            now_utc=now,
        )
    assert out["allow_create"] is True
    assert out["confidence_score"] >= out["threshold"]


def test_evaluate_epic_swot_policy_handles_dict_coverage_values(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    now = datetime(2026, 5, 30, 9, 20, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text("", encoding="utf-8")
    gov = tmp_path / "latest.json"
    gov.write_text(
        json.dumps(
            {
                "event_count": 250,
                "canonical_coverage": {
                    "provider": {"coverage": 0.8},
                    "model": {"value": 0.82},
                    "execution_status": {"pct": 0.9},
                    "task_id": {"ratio": 0.7},
                },
            }
        ),
        encoding="utf-8",
    )
    snap = SimpleNamespace(session_est_tokens=50000, decision="spawn")

    out = session_closeout.evaluate_epic_swot_policy(
        snapshot=snap,
        beads_ready=["a", "b"],
        git={"status_short": ["M a", "M b", "M c", "M d", "M e", "M f"]},
        issues_path=issues,
        governance_path=gov,
        now_utc=now,
    )

    assert "provider" in out["signals"]["low_coverage_fields"]
    assert "task_id" in out["signals"]["low_coverage_fields"]


def test_find_latest_open_swot_epic(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    issues = tmp_path / "issues.jsonl"
    issues.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-old",
                        "title": "EPIC-SWOT NEXT [20260530T090000Z]: Post-Closeout SWOT Seed (2026-05-30)",
                        "issue_type": "epic",
                        "status": "open",
                        "created_at": "2026-05-30T09:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-new",
                        "title": "EPIC-SWOT NEXT [20260530T091000Z]: Post-Closeout SWOT Seed (2026-05-30)",
                        "issue_type": "epic",
                        "status": "open",
                        "created_at": "2026-05-30T09:10:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-closed",
                        "title": "EPIC-SWOT NEXT [20260530T092000Z]: Closed",
                        "issue_type": "epic",
                        "status": "closed",
                        "created_at": "2026-05-30T09:20:00Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    import unittest.mock

    with unittest.mock.patch.object(
        session_closeout, "_fetch_swot_rows_live", return_value=None
    ):
        out = session_closeout.find_latest_open_swot_epic(issues)
    assert out["epic_id"] == "chromatic-harness-v2-new"
    assert out["timestamp_utc"] == "20260530T091000Z"
    assert out["telemetry_key"] == "EPIC-SWOT-NEXT-20260530T091000Z"


def test_apply_epic_swot_aliases_reused_epic_sets_aliases():
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    result = {}
    epic = {
        "ok": False,
        "skipped": True,
        "reused_open_epic": True,
        "telemetry_key": "EPIC-SWOT-NEXT-20260530T091000Z",
        "timestamp_utc": "20260530T091000Z",
        "epic_title": "EPIC-SWOT NEXT [20260530T091000Z]: Post-Closeout SWOT Seed (2026-05-30)",
        "epic_id": "chromatic-harness-v2-new",
        "parent_update": {"ok": False},
    }

    session_closeout._apply_epic_swot_aliases(result, epic)
    assert result["epic_swot_telemetry_key"] == "EPIC-SWOT-NEXT-20260530T091000Z"
    assert result["epic_timestamp_utc"] == "20260530T091000Z"
    assert result["epic_title"].startswith("EPIC-SWOT NEXT")


def test_find_open_swot_task_for_epic(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    issues = tmp_path / "issues.jsonl"
    issues.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-task-old",
                        "title": "Generate next EPIC-SWOT [20260530T090000Z] before final closeout",
                        "issue_type": "task",
                        "status": "open",
                        "created_at": "2026-05-30T09:01:00Z",
                        "dependencies": [
                            {
                                "type": "parent-child",
                                "depends_on_id": "chromatic-harness-v2-epic1",
                            }
                        ],
                    }
                ),
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-task-new",
                        "title": "Generate next EPIC-SWOT [20260530T091000Z] before final closeout",
                        "issue_type": "task",
                        "status": "open",
                        "created_at": "2026-05-30T09:11:00Z",
                        "dependencies": [
                            {
                                "type": "parent-child",
                                "depends_on_id": "chromatic-harness-v2-epic1",
                            }
                        ],
                    }
                ),
                json.dumps(
                    {
                        "id": "chromatic-harness-v2-task-other",
                        "title": "Generate next EPIC-SWOT [20260530T091500Z] before final closeout",
                        "issue_type": "task",
                        "status": "open",
                        "created_at": "2026-05-30T09:15:00Z",
                        "dependencies": [
                            {
                                "type": "parent-child",
                                "depends_on_id": "chromatic-harness-v2-epic2",
                            }
                        ],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    import unittest.mock

    with unittest.mock.patch.object(session_closeout, "_run_bd", return_value=(1, "")):
        out = session_closeout.find_open_swot_task_for_epic(
            "chromatic-harness-v2-epic1", issues
        )
    assert out["task_id"] == "chromatic-harness-v2-task-new"
    assert "EPIC-SWOT" in out["task_title"]


def test_evaluate_epic_swot_policy_respects_external_threshold(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    now = datetime(2026, 5, 30, 9, 20, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text("", encoding="utf-8")
    gov = tmp_path / "latest.json"
    gov.write_text(
        json.dumps(
            {
                "event_count": 800,
                "canonical_coverage": {
                    "provider": 0.6,
                    "model": 0.7,
                    "execution_status": 0.75,
                    "task_id": 0.72,
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = tmp_path / "epic_swot_policy.json"
    cfg.write_text(json.dumps({"confidence_threshold": 0.99}), encoding="utf-8")

    snap = SimpleNamespace(session_est_tokens=180000, decision="spawn")
    out = session_closeout.evaluate_epic_swot_policy(
        snapshot=snap,
        beads_ready=[str(i) for i in range(10)],
        git={"status_short": [f"M f{i}" for i in range(35)]},
        issues_path=issues,
        governance_path=gov,
        policy_config_path=cfg,
        now_utc=now,
    )

    assert out["threshold"] == 0.99
    assert out["allow_create"] is False
