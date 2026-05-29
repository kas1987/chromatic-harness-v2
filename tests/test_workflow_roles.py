"""Tests for workflow task-graph role presets."""

from __future__ import annotations

import json
from pathlib import Path

from workflows.roles import build_standard_pipeline, write_active_graph
from workflows.task_graph import load_task_graph, next_runnable_task

REPO = Path(__file__).resolve().parents[1]


def test_build_standard_pipeline_chain():
    graph = build_standard_pipeline(
        "Ship feature X", bead_id="chromatic-harness-v2-abc"
    )
    assert len(graph["tasks"]) == 4
    assert graph["tasks"][0]["role"] == "scout"
    assert graph["tasks"][1]["depends_on"] == [graph["tasks"][0]["task_id"]]
    assert graph["tasks"][1]["assigned_model"] == "kimi"


def test_write_active_graph_roundtrip(tmp_path: Path):
    graph = build_standard_pipeline("Test", bead_id="test")
    path = write_active_graph(graph, repo_root=tmp_path)
    loaded = load_task_graph(path)
    assert loaded.workflow_id == graph["workflow_id"]
    first = next_runnable_task(loaded)
    assert first is not None
    assert first.role == "scout"


def test_go_deep_writes_graph_subprocess():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "workflow_go.py"), "GO DEEP"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip())
    assert data.get("task_graph_path")
    graph_file = REPO / data["task_graph_path"]
    assert graph_file.is_file()
