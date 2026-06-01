"""Tests for queue<->GitHub mutation mirroring + close-sync + audit trail (gh-51).

Network-free: GH/bd calls are not exercised; pure functions + audit trail only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("queue_sync_mutations", REPO / "scripts" / "queue_sync_mutations.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_bead_id_from_issue_body():
    mod = _load()
    body = "Mirrored from queue.\n\nbead:chromatic-harness-v2-zeky\n\nClose when done."
    assert mod.bead_id_from_issue_body(body) == "chromatic-harness-v2-zeky"
    assert mod.bead_id_from_issue_body("no ref here") is None
    assert mod.bead_id_from_issue_body("") is None


def test_mutation_comment_is_ascii_and_descriptive():
    mod = _load()
    c = mod.mutation_comment("bd-1", "closed")
    c.encode("ascii")
    assert "bd-1" in c and "closed" in c
    assert mod.mutation_comment("bd-2", "claimed").endswith("claimed by an agent.")


def test_beads_to_close_from_closed_issues():
    mod = _load()
    issues = [
        {"number": 1, "state": "closed", "body": "bead:bd-a"},
        {"number": 2, "state": "open", "body": "bead:bd-b"},  # open -> skip
        {"number": 3, "state": "closed", "body": "no ref"},  # no bead -> skip
        {"number": 4, "state": "CLOSED", "body": "bead:bd-d"},  # case-insensitive
    ]
    out = mod.beads_to_close_from_closed_issues(issues)
    ids = {o["bead_id"] for o in out}
    assert ids == {"bd-a", "bd-d"}
    assert all("issue_number" in o for o in out)


def test_record_and_read_history(tmp_path):
    mod = _load()
    h = tmp_path / "queue_sync" / "history.jsonl"
    mod.record_sync_action("create", "bd-1", 10, timestamp="T1", path=h)
    mod.record_sync_action("inbound_close", "bd-2", 11, timestamp="T2", extra={"result": "bead_closed"}, path=h)
    rows = mod.read_history(h)
    assert len(rows) == 2
    assert rows[0]["action"] == "create" and rows[0]["bead_id"] == "bd-1"
    assert rows[1]["result"] == "bead_closed"
    # every required audit field present (eval 5)
    for r in rows:
        assert {"timestamp", "action", "bead_id", "issue_number"} <= set(r)


def test_read_history_skips_partial_lines(tmp_path):
    mod = _load()
    h = tmp_path / "history.jsonl"
    h.parent.mkdir(parents=True, exist_ok=True)
    h.write_text('{"action":"ok","timestamp":"T","bead_id":"x","issue_number":1}\n{partial', encoding="utf-8")
    rows = mod.read_history(h)
    assert len(rows) == 1  # partial line skipped, no crash


def test_read_history_missing_file(tmp_path):
    mod = _load()
    assert mod.read_history(tmp_path / "nope.jsonl") == []


def test_mirror_mutation_dry_run_records_history(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "HISTORY", tmp_path / "history.jsonl")
    monkeypatch.setattr(mod, "_find_issue_for_bead", lambda bid: {"number": 42, "body": f"bead:{bid}"})
    res = mod.mirror_mutation("bd-x", "closed", timestamp="T", execute=False)
    assert res["status"] == "dry_run"
    assert res["issue_number"] == 42
    rows = mod.read_history(tmp_path / "history.jsonl")
    assert rows and rows[0]["action"] == "mutation_mirror"


def test_mirror_mutation_no_linked_issue(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_find_issue_for_bead", lambda bid: None)
    res = mod.mirror_mutation("bd-x", "claimed", timestamp="T", execute=False)
    assert res["status"] == "no_linked_issue"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
