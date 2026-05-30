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
    monkeypatch.setattr(
        session_closeout, "build_transfer_packet", lambda *args, **kwargs: {"ok": True}
    )
    monkeypatch.setattr(
        session_closeout, "write_transfer_artifacts", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(session_closeout, "log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        session_closeout, "evaluate_epic_swot_policy", fake_evaluate_epic_swot_policy
    )
    monkeypatch.setattr(
        session_closeout, "find_latest_open_swot_epic", lambda *args, **kwargs: {}
    )
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
    import unittest.mock

    # When live query succeeds with empty list (no open epics), creation is allowed.
    with (
        unittest.mock.patch.object(
            session_closeout, "_fetch_swot_rows_live", return_value=[]
        ),
        unittest.mock.patch.object(
            session_closeout, "_fetch_pending_swot_tasks_live", return_value=[]
        ),
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

    # When live query fails (bd unavailable), creation is blocked to prevent duplicate spam.
    with (
        unittest.mock.patch.object(
            session_closeout, "_fetch_swot_rows_live", return_value=None
        ),
        unittest.mock.patch.object(
            session_closeout, "_fetch_pending_swot_tasks_live", return_value=None
        ),
    ):
        out_fail_closed = session_closeout.evaluate_epic_swot_policy(
            snapshot=snap,
            beads_ready=[str(i) for i in range(9)],
            git={"status_short": [f"M f{i}" for i in range(30)]},
            issues_path=issues,
            governance_path=gov,
            now_utc=now,
        )
    assert out_fail_closed["allow_create"] is False
    assert "bd live query failed" in out_fail_closed["decision_reason"]


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


def test_load_epic_swot_policy_config_rejects_invalid_scalar_ranges(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    cfg = tmp_path / "epic_swot_policy.json"
    cfg.write_text(
        json.dumps(
            {
                "confidence_threshold": 1.5,
                "block_penalty": -0.1,
                "coverage": {
                    "min_field_coverage": "bad",
                    "field_weight": 2,
                    "max_bonus": -1,
                    "fields": "provider",
                },
            }
        ),
        encoding="utf-8",
    )

    out = session_closeout._load_epic_swot_policy_config(cfg)

    assert out["confidence_threshold"] == 0.55
    assert out["block_penalty"] == 0.8
    assert out["coverage"]["min_field_coverage"] == 0.85
    assert out["coverage"]["field_weight"] == 0.04
    assert out["coverage"]["max_bonus"] == 0.14
    assert out["coverage"]["fields"] == [
        "provider",
        "model",
        "execution_status",
        "task_id",
    ]


def test_load_epic_swot_policy_config_rejects_invalid_nested_thresholds(tmp_path: Path):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    cfg = tmp_path / "epic_swot_policy.json"
    cfg.write_text(
        json.dumps(
            {
                "history_windows": {"recent_open_hours": 0, "rolling_days": -5},
                "history_limits": {"open_swot_total_cap": 0},
                "session_tokens": {"high": {"min": -1, "score": 5}},
            }
        ),
        encoding="utf-8",
    )

    out = session_closeout._load_epic_swot_policy_config(cfg)

    assert out["history_windows"]["recent_open_hours"] == 8
    assert out["history_windows"]["rolling_days"] == 7
    assert out["history_limits"]["open_swot_total_cap"] == 1
    assert out["session_tokens"]["high"]["min"] == 120000
    assert out["session_tokens"]["high"]["score"] == 0.24


def test_load_swot_epic_history_uses_live_query_when_available(tmp_path: Path):
    """Live bd query result takes precedence over stale JSONL."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402
    import unittest.mock

    now = datetime(2026, 5, 30, 10, 0, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    # JSONL has no open rows — live query has one open row
    issues.write_text("", encoding="utf-8")
    live_row = {
        "id": "chromatic-harness-v2-live",
        "title": "EPIC-SWOT NEXT [20260530T095000Z]: Live",
        "issue_type": "epic",
        "status": "open",
        "created_at": "2026-05-30T09:50:00Z",
    }
    with unittest.mock.patch.object(
        session_closeout, "_fetch_swot_rows_live", return_value=[live_row]
    ):
        stats = session_closeout._load_swot_epic_history(
            issues_path=issues, now_utc=now
        )
    assert stats["open_swot_total"] == 1


def test_load_swot_epic_history_falls_back_to_jsonl(tmp_path: Path):
    """When live query returns None, JSONL provides the history data."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402
    import unittest.mock

    now = datetime(2026, 5, 30, 10, 0, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text(
        json.dumps(
            {
                "id": "chromatic-harness-v2-jsonl",
                "title": "EPIC-SWOT NEXT [20260530T090000Z]: JSONL",
                "issue_type": "epic",
                "status": "open",
                "created_at": "2026-05-30T09:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    with unittest.mock.patch.object(
        session_closeout, "_fetch_swot_rows_live", return_value=None
    ):
        stats = session_closeout._load_swot_epic_history(
            issues_path=issues, now_utc=now
        )
    assert stats["open_swot_total"] == 1


def test_load_swot_epic_history_cap_enforced(tmp_path: Path):
    """open_swot_total_cap=1: policy blocks when live query returns 2 open SWOT epics."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402
    import unittest.mock

    now = datetime(2026, 5, 30, 10, 0, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text("", encoding="utf-8")
    gov = tmp_path / "gov.json"
    gov.write_text(
        json.dumps({"event_count": 0, "canonical_coverage": {}}), encoding="utf-8"
    )
    live_rows = [
        {
            "id": f"chromatic-harness-v2-swot-{i}",
            "title": f"EPIC-SWOT NEXT [202605300900{i:02d}Z]: Seed",
            "issue_type": "epic",
            "status": "open",
            "created_at": f"2026-05-30T09:00:0{i}Z",
        }
        for i in range(2)
    ]
    snap = __import__("types").SimpleNamespace(
        session_est_tokens=50000, decision="spawn"
    )
    with unittest.mock.patch.object(
        session_closeout, "_fetch_swot_rows_live", return_value=live_rows
    ):
        out = session_closeout.evaluate_epic_swot_policy(
            snapshot=snap,
            beads_ready=[],
            git={"status_short": []},
            issues_path=issues,
            governance_path=gov,
            now_utc=now,
        )
    assert out["allow_create"] is False
    assert "open EPIC-SWOT" in out["decision_reason"]


def test_load_swot_epic_history_counts_in_progress(tmp_path: Path):
    """in_progress SWOT epics count toward open_swot_total (not just 'open')."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402
    import unittest.mock

    now = datetime(2026, 5, 30, 10, 0, 0, tzinfo=timezone.utc)
    issues = tmp_path / "issues.jsonl"
    issues.write_text("", encoding="utf-8")
    live_row = {
        "id": "chromatic-harness-v2-wip",
        "title": "EPIC-SWOT NEXT [20260530T090000Z]: WIP",
        "issue_type": "epic",
        "status": "in_progress",
        "created_at": "2026-05-30T09:00:00Z",
    }
    with unittest.mock.patch.object(
        session_closeout, "_fetch_swot_rows_live", return_value=[live_row]
    ):
        stats = session_closeout._load_swot_epic_history(
            issues_path=issues, now_utc=now
        )
    assert stats["open_swot_total"] == 1


def test_write_auto_turn_post_mortem_creates_file(tmp_path: Path, monkeypatch):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

    monkeypatch.setattr(session_closeout, "_REPO", tmp_path)
    result = {
        "invoked_by": "cli",
        "budget": {"decision": "spawn"},
        "epic_swot_policy": {
            "allow_create": True,
            "confidence_score": 0.82,
            "decision_reason": "allow",
        },
        "auto_turn": {"harvest_mode": "session_end"},
        "closeout_telemetry_path": ".agents/handoffs/closeout_telemetry_latest.json",
        "closeout_telemetry_history_path": ".agents/handoffs/closeout_telemetry_20260530T120000Z.json",
        "auto_start_ok": True,
    }

    rel = session_closeout._write_auto_turn_post_mortem(
        result,
        auto_turn_index=5,
        auto_turn_threshold=5,
    )
    out = tmp_path / rel

    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "Post-Mortem Council Report - Auto Turn Closeout" in text
    assert "auto_turn_index: 5" in text
    assert "harvest_mode: session_end" in text


def test_main_auto_turn_threshold_triggers_post_mortem_and_session_end_harvest(
    tmp_path: Path, monkeypatch
):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

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

    run_calls: list[list[str]] = []

    def fake_run(cmd, *, timeout=120, cwd=None):
        run_calls.append(cmd)
        return 0, "ok"

    monkeypatch.setattr(session_closeout, "_REPO", tmp_path)
    monkeypatch.setattr(session_closeout, "BudgetLedger", FakeLedger)
    monkeypatch.setattr(session_closeout, "git_snapshot", lambda: {"status_short": []})
    monkeypatch.setattr(session_closeout, "beads_ready_ids", lambda: [])
    monkeypatch.setattr(
        session_closeout,
        "write_handoff",
        lambda *args, **kwargs: tmp_path / "12_HANDOFFS" / "handoff.md",
    )
    monkeypatch.setattr(
        session_closeout, "build_transfer_packet", lambda *args, **kwargs: {"ok": True}
    )
    monkeypatch.setattr(
        session_closeout, "write_transfer_artifacts", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(session_closeout, "log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        session_closeout,
        "_write_closeout_telemetry_snapshot",
        lambda result: {"latest": "latest.json", "history": "history.json"},
    )
    monkeypatch.setattr(session_closeout, "_run", fake_run)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "session_closeout.py",
            "--invoked-by",
            "cli",
            "--no-epic-swot",
            "--no-auto-start-next-agent",
            "--auto-turn-index",
            "5",
            "--auto-turn-threshold",
            "5",
        ],
    )

    stdout = StringIO()
    with redirect_stdout(stdout):
        rc = session_closeout.main()

    assert rc == 0
    payload = json.loads(stdout.getvalue())
    assert payload["auto_turn"]["triggered_closeout"] is True
    assert payload["auto_turn"]["harvest_mode"] == "session_end"
    assert payload["auto_turn"]["artifact_kind"] == "post_mortem"
    assert payload["auto_turn"]["post_mortem_path"]
    assert (tmp_path / payload["auto_turn"]["post_mortem_path"]).is_file()
    assert payload["auto_turn"]["observation_log_path"]
    assert (tmp_path / payload["auto_turn"]["observation_log_path"]).is_file()

    harvest_call = next(
        call
        for call in run_calls
        if "harvest_rigs.py" in " ".join(str(x) for x in call)
    )
    assert "--execute" in harvest_call
    assert "--session-end" in harvest_call


def test_main_auto_turn_uses_checkpoint_when_tasks_open(tmp_path: Path, monkeypatch):
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout  # noqa: E402

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

    def fake_run(cmd, *, timeout=120, cwd=None):
        return 0, "1\t2\tfoo.py" if cmd[:4] == [
            "git",
            "diff",
            "--numstat",
            "HEAD",
        ] else "ok"

    monkeypatch.setattr(session_closeout, "_REPO", tmp_path)
    monkeypatch.setattr(session_closeout, "BudgetLedger", FakeLedger)
    monkeypatch.setattr(
        session_closeout, "git_snapshot", lambda: {"status_short": [" M foo.py"]}
    )
    monkeypatch.setattr(session_closeout, "beads_ready_ids", lambda: ["bead-1"])
    monkeypatch.setattr(
        session_closeout,
        "write_handoff",
        lambda *args, **kwargs: tmp_path / "12_HANDOFFS" / "handoff.md",
    )
    monkeypatch.setattr(
        session_closeout, "build_transfer_packet", lambda *args, **kwargs: {"ok": True}
    )
    monkeypatch.setattr(
        session_closeout, "write_transfer_artifacts", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(session_closeout, "log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        session_closeout,
        "_write_closeout_telemetry_snapshot",
        lambda result: {"latest": "latest.json", "history": "history.json"},
    )
    monkeypatch.setattr(session_closeout, "_run", fake_run)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "session_closeout.py",
            "--invoked-by",
            "cli",
            "--no-epic-swot",
            "--no-auto-start-next-agent",
            "--auto-turn-index",
            "5",
            "--auto-turn-threshold",
            "5",
        ],
    )

    stdout = StringIO()
    with redirect_stdout(stdout):
        rc = session_closeout.main()

    assert rc == 0
    payload = json.loads(stdout.getvalue())
    assert payload["auto_turn"]["triggered_closeout"] is True
    assert payload["auto_turn"]["artifact_kind"] == "checkpoint"

    artifact = tmp_path / payload["auto_turn"]["post_mortem_path"]
    assert artifact.is_file()
    text = artifact.read_text(encoding="utf-8")
    assert "Learning Checkpoint Report - Auto Turn Closeout" in text
    assert "artifact_kind: checkpoint" in text

    obs = tmp_path / payload["auto_turn"]["observation_log_path"]
    assert obs.is_file()
    line = obs.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(line)
    assert row["artifact_kind"] == "checkpoint"
    assert row["loc_insertions"] == 1
    assert row["loc_deletions"] == 2


# ── _emit_injected_learning_outcomes tests ─────────────────────────────────


def test_emit_outcomes_no_injected_file(tmp_path, monkeypatch):
    """Returns ok=False with skip_reason when injected_learnings.json is absent."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout

    monkeypatch.setattr(
        session_closeout, "_INJECTED_LEARNINGS", tmp_path / "missing.json"
    )
    monkeypatch.setattr(session_closeout, "_EXECUTION_LOG", tmp_path / "exec.jsonl")
    result = session_closeout._emit_injected_learning_outcomes()
    assert result["ok"] is False
    assert "skip_reason" in result


def test_emit_outcomes_success_path(tmp_path, monkeypatch):
    """Emits applied_success when no error events found after injection."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout

    now = "2026-05-30T10:00:00+00:00"
    injected = tmp_path / "injected_learnings.json"
    injected.write_text(
        json.dumps(
            {
                "injected_at": now,
                "terms": ["router"],
                "learnings": [
                    {
                        "name": "my-learning",
                        "path": "/repo/.agents/learnings/my-learning.md",
                        "title": "My Learning",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # Execution log has only a normal event after injection
    exec_log = tmp_path / "execution.jsonl"
    exec_log.write_text(
        json.dumps(
            {
                "ts": "2026-05-30T10:01:00+00:00",
                "event_type": "workflow.go_audit",
                "workflow_decision": "ok",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    usage_log = tmp_path / "learning_usage.jsonl"
    usage_log.write_text("", encoding="utf-8")

    import unittest.mock

    monkeypatch.setattr(session_closeout, "_INJECTED_LEARNINGS", injected)
    monkeypatch.setattr(session_closeout, "_EXECUTION_LOG", exec_log)
    with unittest.mock.patch("activity.log._usage_log_path", return_value=usage_log):
        result = session_closeout._emit_injected_learning_outcomes()

    assert result["ok"] is True
    assert result["outcome"] == "applied_success"
    assert result["had_error"] is False
    assert any(e["name"] == "my-learning" for e in result["emitted"])


def test_emit_outcomes_failure_path(tmp_path, monkeypatch):
    """Emits applied_failure when an error event is found after injection."""
    sys.path.insert(0, str(_REPO / "scripts"))
    import session_closeout

    now = "2026-05-30T10:00:00+00:00"
    injected = tmp_path / "injected_learnings.json"
    injected.write_text(
        json.dumps(
            {
                "injected_at": now,
                "terms": [],
                "learnings": [
                    {"name": "my-learning", "path": "", "title": "My Learning"}
                ],
            }
        ),
        encoding="utf-8",
    )
    exec_log = tmp_path / "execution.jsonl"
    exec_log.write_text(
        json.dumps(
            {
                "ts": "2026-05-30T10:02:00+00:00",
                "event_type": "workflow.error",
                "workflow_decision": "error",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    usage_log = tmp_path / "learning_usage.jsonl"
    usage_log.write_text("", encoding="utf-8")

    import unittest.mock

    monkeypatch.setattr(session_closeout, "_INJECTED_LEARNINGS", injected)
    monkeypatch.setattr(session_closeout, "_EXECUTION_LOG", exec_log)
    with unittest.mock.patch("activity.log._usage_log_path", return_value=usage_log):
        result = session_closeout._emit_injected_learning_outcomes()

    assert result["ok"] is True
    assert result["outcome"] == "applied_failure"
    assert result["had_error"] is True
