"""Self-heal cycle JSON shape (mocked subprocess)."""

from __future__ import annotations

import json
from unittest.mock import patch

import scripts.workflow_self_heal_cycle as cycle


def test_self_heal_cycle_shape_when_not_self_heal(monkeypatch):
    first = {"decision": "execute", "bead_id": "chromatic-harness-v2-abc", "_returncode": 0}
    monkeypatch.setattr(cycle, "_run_go", lambda: first)
    intake = patch.object(cycle, "_run_auto_intake")
    with intake as mock_intake:
        monkeypatch.setattr("sys.argv", ["workflow_self_heal_cycle.py"])
        rc = cycle.main()
    mock_intake.assert_not_called()
    assert rc == 0


def test_self_heal_cycle_runs_intake_and_second_go(monkeypatch, capsys):
    calls = [
        {"decision": "self_heal", "bead_id": "x", "_returncode": 0},
        {"decision": "execute", "bead_id": "y", "_returncode": 0},
    ]

    def fake_go():
        return calls.pop(0)

    monkeypatch.setattr(cycle, "_run_go", fake_go)
    monkeypatch.setattr(
        cycle,
        "_run_auto_intake",
        lambda limit: {"processed": 2, "_returncode": 0},
    )
    monkeypatch.setattr(
        "sys.argv",
        ["workflow_self_heal_cycle.py", "--limit", "3"],
    )
    rc = cycle.main()
    out = json.loads(capsys.readouterr().out)
    assert out["cycled"] is True
    assert out["intake"]["processed"] == 2
    assert len(out["passes"]) == 3
    assert rc == 0
