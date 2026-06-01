"""OBS-007: .vscode/tasks.json exposes observability tasks; docs explain them.

Validates structure and portability of the IDE task definitions without
launching an editor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TASKS_JSON = REPO / ".vscode" / "tasks.json"
IDE_DOC = REPO / "docs" / "IDE_SETUP.md"

REQUIRED_SCRIPTS = [
    "validate_event_schema.py",  # validate logs
    "detect_file_collisions.py",  # detect collisions
    "snapshot_git_state.py",  # snapshot git
    "summarize_error_patterns.py",  # summarize errors
]


def _tasks() -> list[dict]:
    data = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    return data["tasks"]


def test_tasks_json_is_valid_json():
    data = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    assert data["version"] == "2.0.0"
    assert isinstance(data["tasks"], list) and data["tasks"]


def test_required_observability_scripts_are_wired():
    commands = " ".join(t.get("command", "") for t in _tasks() if isinstance(t.get("command"), str))
    for script in REQUIRED_SCRIPTS:
        assert script in commands, f"tasks.json missing a task invoking {script}"


def test_observability_tasks_present_by_label():
    labels = {t.get("label", "") for t in _tasks()}
    for needed in [
        "Observability: Validate event logs",
        "Observability: Detect file collisions",
        "Observability: Snapshot git state",
        "Observability: Summarize error patterns",
    ]:
        assert needed in labels, f"missing task label: {needed}"


def test_existing_tasks_preserved():
    # The merge must not drop pre-existing Chromatic/Harness tasks.
    labels = {t.get("label", "") for t in _tasks()}
    assert "Chromatic: Validate visual registry" in labels
    assert "Harness: Session Status" in labels


def test_observability_tasks_avoid_shell_specific_operators():
    # Portability (OBS-007 acceptance): the observability tasks must not rely
    # on shell-specific operators. Scoped to "Observability:" tasks — legacy
    # Harness tasks may intentionally chain with ';'.
    forbidden = ["&&", "||", "|", ">", "<", ";"]
    for t in _tasks():
        if not t.get("label", "").startswith("Observability:"):
            continue
        cmd = t.get("command")
        if not isinstance(cmd, str):
            continue
        for tok in forbidden:
            assert tok not in cmd, f"task {t.get('label')!r} uses non-portable operator {tok!r}"


def test_ide_setup_doc_documents_each_task():
    assert IDE_DOC.is_file(), "docs/IDE_SETUP.md missing"
    text = IDE_DOC.read_text(encoding="utf-8")
    for script in REQUIRED_SCRIPTS:
        assert script in text, f"IDE_SETUP.md does not document {script}"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
