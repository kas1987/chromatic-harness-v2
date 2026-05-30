"""Regression tests for delegation observability correlation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import claude_delegation_observability as cdo  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_observability_matches_by_run_and_task_id(tmp_path: Path) -> None:
    run_id = "bhloop-20260530T000000Z-123"
    task_id = "chromatic-harness-v2-4n4-delegation-c1"
    bead_id = "chromatic-harness-v2-4n4"

    packet = tmp_path / "packet.json"
    prompt = tmp_path / "prompt.md"
    autoloop = tmp_path / "autoloop.json"
    governance = tmp_path / "governance.json"
    workflow_log = tmp_path / "workflow.jsonl"
    agent_log = tmp_path / "agent.jsonl"

    _write_json(
        packet,
        {
            "decision": "execute",
            "pre_swarm_gate": {"ok": True},
            "task": "delegate remediation",
            "bead_id": bead_id,
            "run_id": run_id,
            "task_id": task_id,
            "provider_choices": [{"provider": "openai", "model": "gpt-5.3-codex"}],
        },
    )
    prompt.write_text("# Prompt\n", encoding="utf-8")
    _write_json(autoloop, {"cycles": [{"claude_delegate": {"returncode": 0}}]})
    _write_json(
        governance,
        {
            "canonical_coverage": {
                "task_id": {"coverage": 0.8},
                "provider": {"coverage": 0.8},
                "model": {"coverage": 0.8},
                "execution_status": {"coverage": 0.8},
            }
        },
    )

    workflow_log.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": task_id,
                "provider": "openai",
                "model": "gpt-5.3-codex",
                "execution_status": "execute",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agent_log.write_text("", encoding="utf-8")

    args = argparse.Namespace(
        packet=str(packet),
        prompt=str(prompt),
        autoloop=str(autoloop),
        governance=str(governance),
        workflow_log=str(workflow_log),
        agent_log=str(agent_log),
        bead_id=bead_id,
        run_id=run_id,
        task_id=task_id,
        task_contains="",
        max_log_lines=200,
        write=False,
        extras=[],
    )

    report = cdo.build_report(args)
    assert report["status"] == "green"
    assert report["pickup_evidence"]["workflow_matches"] == 1
    assert report["delegation"]["run_id"] == run_id
    assert report["delegation"]["task_id"] == task_id
