"""Tests for scripts/root_artifact_hygiene.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import root_artifact_hygiene as rah


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "07_LOGS_AND_AUDIT" / "root_artifacts").mkdir(parents=True)
    monkeypatch.setattr(rah, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        rah,
        "ARTIFACT_DIR",
        tmp_path / "07_LOGS_AND_AUDIT" / "root_artifacts",
    )
    return tmp_path


def test_plan_actions_move_and_delete(fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    # Move candidate.
    (fake_repo / ".tmp_example.json").write_text("{}", encoding="utf-8")
    # Delete candidates.
    (fake_repo / ".coverage").write_text("cov", encoding="utf-8")
    (fake_repo / ".tmp_ingest").mkdir()

    monkeypatch.setattr(rah, "_is_tracked", lambda _p: True)
    monkeypatch.setattr(rah, "_is_ignored", lambda _p: False)

    actions = rah.plan_actions()
    by_path = {a.path: a for a in actions}

    assert by_path[".tmp_example.json"].action == "move"
    assert by_path[".coverage"].action == "delete"
    assert by_path[".tmp_ingest"].action == "delete_dir"


def test_apply_actions_write_changes_fs(fake_repo: Path):
    src_move = fake_repo / ".tmp_sample.txt"
    src_move.write_text("data", encoding="utf-8")
    src_del = fake_repo / "check_files.log"
    src_del.write_text("log", encoding="utf-8")

    actions = [
        rah.Action(
            action="move",
            path=".tmp_sample.txt",
            destination="07_LOGS_AND_AUDIT/root_artifacts/.tmp_sample.txt",
            existed=True,
            applied=False,
            reason="test",
        ),
        rah.Action(
            action="delete",
            path="check_files.log",
            destination=None,
            existed=True,
            applied=False,
            reason="test",
        ),
    ]

    rah.apply_actions(actions, write=True)

    assert not src_move.exists()
    assert (fake_repo / "07_LOGS_AND_AUDIT" / "root_artifacts" / ".tmp_sample.txt").is_file()
    assert not src_del.exists()
    assert all(a.applied for a in actions)


def test_apply_actions_dry_run_no_changes(fake_repo: Path):
    src = fake_repo / ".tmp_keep.txt"
    src.write_text("keep", encoding="utf-8")

    actions = [
        rah.Action(
            action="move",
            path=".tmp_keep.txt",
            destination="07_LOGS_AND_AUDIT/root_artifacts/.tmp_keep.txt",
            existed=True,
            applied=False,
            reason="test",
        )
    ]

    rah.apply_actions(actions, write=False)

    assert src.is_file()
    assert not actions[0].applied


def test_write_report_outputs_counts(fake_repo: Path):
    report = fake_repo / "07_LOGS_AND_AUDIT" / "root_artifacts" / "out.json"
    actions = [
        rah.Action(
            action="move",
            path="a",
            destination="b",
            existed=True,
            applied=True,
            reason="x",
        ),
        rah.Action(
            action="delete",
            path="c",
            destination=None,
            existed=False,
            applied=False,
            reason="y",
        ),
    ]

    rah.write_report(report, actions, write=True)

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["mode"] == "write"
    assert payload["counts"]["planned"] == 2
    assert payload["counts"]["applied"] == 1
    assert payload["counts"]["missing"] == 1
