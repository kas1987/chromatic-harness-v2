"""Tests for event lifecycle tools: find, update, report (OBS-011)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _log_event(repo_root: Path, event_id: str, status: str = "open", event_type: str = "error") -> None:
    subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/log_harness_event.py"),
            "--repo-root",
            str(repo_root),
            "--event-id",
            event_id,
            "--event-type",
            event_type,
            "--severity",
            "medium",
            "--category",
            "command_failure",
            "--status",
            status,
            "--surface",
            "terminal",
            "--raw-excerpt",
            "test event",
            "--log-path",
            str(repo_root / "00_META/observability/ERROR_LOG.jsonl"),
        ],
        check=True,
        capture_output=True,
    )


def _update_status(repo_root: Path, event_id: str, status: str) -> None:
    subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/update_event_status.py"),
            "--repo-root",
            str(repo_root),
            "--event-id",
            event_id,
            "--status",
            status,
        ],
        check=True,
        capture_output=True,
    )


class TestFindEvent:
    def test_find_event_by_id(self, tmp_path: Path):
        log_dir = tmp_path / "00_META" / "observability"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "ERROR_LOG.jsonl"
        log_file.write_text(json.dumps({"event_id": "EV-001", "message": "hello"}) + "\n")

        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/find_event.py"), "--repo-root", str(tmp_path), "--event-id", "EV-001"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        assert data["event_id"] == "EV-001"

    def test_find_event_missing(self, tmp_path: Path):
        log_dir = tmp_path / "00_META" / "observability"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "ERROR_LOG.jsonl").write_text("")

        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/find_event.py"), "--repo-root", str(tmp_path), "--event-id", "MISSING"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr


class TestUpdateEventStatus:
    def test_appends_status_update(self, tmp_path: Path):
        log_dir = tmp_path / "00_META" / "observability"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "ERROR_LOG.jsonl").write_text("")

        _log_event(tmp_path, "EV-002", status="open")
        _update_status(tmp_path, "EV-002", "resolved")

        lines = (log_dir / "ERROR_LOG.jsonl").read_text().splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        assert len(events) == 2
        assert events[0]["event_id"] == "EV-002"
        assert events[0]["event_type"] == "error"
        assert events[1]["event_type"] == "status_update"
        assert events[1]["raw_excerpt"] == "Status update for EV-002"


class TestGenerateObservabilityReport:
    def test_computes_latest_status_from_lifecycle(self, tmp_path: Path):
        log_dir = tmp_path / "00_META" / "observability"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "ERROR_LOG.jsonl").write_text("")

        _log_event(tmp_path, "EV-003", status="open")
        _update_status(tmp_path, "EV-003", "resolved")

        report_path = tmp_path / "report.md"
        subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/generate_observability_report.py"),
                "--repo-root",
                str(tmp_path),
                "--out",
                str(report_path),
            ],
            check=True,
            capture_output=True,
        )

        report = report_path.read_text()
        # The report should show resolved in status counts, not just open
        assert "resolved" in report
        # The report should not list EV-003 under open events
        # (since latest status is resolved)
        open_section = report.split("## Open / Routed Events")[1]
        assert "EV-003" not in open_section
