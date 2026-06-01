"""Tests for scripts/triage_drift_findings.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import triage_drift_findings as triage


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".agents" / "evolve").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(triage, "REPO", tmp_path)
    return tmp_path


def test_load_drift_items_jsonl(fake_repo: Path):
    latest = fake_repo / ".agents" / "evolve" / "drift-findings-latest.jsonl"
    latest.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "category": "broken_link",
                        "file": "docs/README.md",
                        "line": 42,
                        "detail": "broken link found",
                    }
                ),
                json.dumps(
                    {
                        "code": "todo",
                        "path": "scripts/x.py",
                        "message": "todo remains",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    items = triage.load_drift_items(fake_repo)
    assert len(items) == 2
    assert any(i.category == "broken_link" for i in items)
    assert any(i.category == "todo" for i in items)


def test_triage_write_creates_and_updates_state(fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    latest = fake_repo / ".agents" / "evolve" / "drift-findings-latest.jsonl"
    latest.write_text(
        json.dumps(
            {
                "category": "missing_file",
                "file": "docs/MISSING.md",
                "line": 1,
                "detail": "missing file",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created_cmds: list[list[str]] = []

    def fake_run_bd(args: list[str], *, cwd: Path):
        created_cmds.append(args)
        return 0, "Created issue: chromatic-harness-v2-test"

    monkeypatch.setattr(triage, "_run_bd", fake_run_bd)

    state = fake_repo / ".agents" / "evolve" / "drift-triage-state.json"
    result = triage.triage(
        root=fake_repo,
        write=True,
        max_items=5,
        state_path=state,
    )

    assert result["created_count"] == 1
    assert created_cmds and created_cmds[0][0] == "create"
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert len(saved.get("created_fingerprints") or []) == 1
