"""Tests for the playbook evolution feedback loop (chromatic-harness-v2-7d2.5)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location("propose_playbook_evolution", _SCRIPTS / "propose_playbook_evolution.py")
ppe = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(ppe)


def _entry(**kw):
    base = {
        "ts": "2026-06-02T00:00:00+00:00",
        "mission_id": "",
        "task_id": "t",
        "gate": "confidence",
        "input_score": None,
        "band": "low",
        "action": "ok",
        "reason": "",
        "lesson": "",
    }
    base.update(kw)
    return base


def test_route_playbook_keyword_and_default():
    assert ppe.route_playbook("model routing was wrong") == "MODEL_ROUTING_PLAYBOOK.md"
    assert ppe.route_playbook("bd dolt push failed") == "BEADS_PLAYBOOK.md"
    # No keyword overlap -> orchestrator fallback.
    assert ppe.route_playbook("totally novel situation") == "ORCHESTRATOR_PLAYBOOK.md"


def test_recurring_lesson_becomes_proposal():
    entries = [_entry(lesson="always rebase before push") for _ in range(3)]
    props = ppe.detect_signals(entries, threshold=3)
    lessons = [p for p in props if p["kind"] == "codify_lesson"]
    assert len(lessons) == 1
    assert lessons[0]["count"] == 3
    assert lessons[0]["signal"] == "always rebase before push"


def test_below_threshold_is_ignored():
    entries = [_entry(lesson="rare one")]  # only once
    assert ppe.detect_signals(entries, threshold=3) == []


def test_low_band_escalation_tunes_gate():
    entries = [_entry(band="low", action="escalate") for _ in range(4)]
    props = ppe.detect_signals(entries, threshold=3)
    gate = [p for p in props if p["kind"] == "tune_gate"]
    assert len(gate) == 1
    assert gate[0]["count"] == 4
    assert gate[0]["playbook"] == "ORCHESTRATOR_PLAYBOOK.md"


def test_high_band_proceed_is_not_flagged():
    # Confident proceeds need no playbook fix — must not generate proposals.
    entries = [_entry(band="high", action="proceed") for _ in range(10)]
    assert ppe.detect_signals(entries, threshold=3) == []


def test_failure_reason_cluster_adds_fix_pattern():
    entries = [_entry(action="replan", reason="intake parser returned empty") for _ in range(3)]
    props = ppe.detect_signals(entries, threshold=3)
    fixes = [p for p in props if p["kind"] == "add_fix_pattern"]
    assert len(fixes) == 1
    # "intake" routes to the beads playbook (intake -> bead creation).
    assert fixes[0]["playbook"] == "BEADS_PLAYBOOK.md"


def test_noise_reasons_are_filtered_out():
    # "bd show <id>" is routine navigation logged as reason, not a failure.
    entries = [_entry(action="replan", reason="bd show chromatic-harness-v2-abc") for _ in range(5)]
    props = ppe.detect_signals(entries, threshold=3)
    assert [p for p in props if p["kind"] == "add_fix_pattern"] == []


def test_is_noise_reason_predicate():
    assert ppe.is_noise_reason("bd show foo") is True
    assert ppe.is_noise_reason("git status") is True
    assert ppe.is_noise_reason("intake parser crashed") is False


def test_proposals_sorted_by_count_desc():
    entries = [_entry(lesson="A") for _ in range(3)] + [_entry(lesson="B") for _ in range(7)]
    props = ppe.detect_signals(entries, threshold=3)
    assert [p["count"] for p in props] == sorted([p["count"] for p in props], reverse=True)


def test_load_decisions_tolerates_torn_line(tmp_path):
    log = tmp_path / "decision_log.jsonl"
    good = json.dumps(_entry(lesson="ok"))
    log.write_text(good + "\n{ partial torn line", encoding="utf-8")
    loaded = ppe._load_decisions(log, window=0)
    assert len(loaded) == 1
    assert loaded[0]["lesson"] == "ok"


def test_window_limits_to_tail(tmp_path):
    log = tmp_path / "decision_log.jsonl"
    rows = [json.dumps(_entry(lesson=f"L{i}")) for i in range(10)]
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    loaded = ppe._load_decisions(log, window=3)
    assert len(loaded) == 3
    assert loaded[-1]["lesson"] == "L9"


def test_end_to_end_writes_staging_files(tmp_path):
    root = tmp_path
    dec = root / "07_LOGS_AND_AUDIT" / "decisions"
    dec.mkdir(parents=True)
    rows = [json.dumps(_entry(lesson="always push before done")) for _ in range(3)]
    (dec / "decision_log.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")

    argv = sys.argv
    sys.argv = ["propose_playbook_evolution", "--repo-root", str(root), "--threshold", "3"]
    try:
        ppe.main()
    finally:
        sys.argv = argv

    md = root / "00_META" / "observability" / "PLAYBOOK_EVOLUTION_PROPOSALS.md"
    jsonl = root / "00_META" / "observability" / "playbook_evolution_proposals.jsonl"
    assert md.exists()
    assert "always push before done" in md.read_text(encoding="utf-8")
    assert jsonl.exists()
    lines = [json.loads(x) for x in jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lines and lines[0]["count"] == 3


def test_dry_run_writes_nothing(tmp_path, capsys):
    root = tmp_path
    dec = root / "07_LOGS_AND_AUDIT" / "decisions"
    dec.mkdir(parents=True)
    rows = [json.dumps(_entry(lesson="dry run lesson")) for _ in range(3)]
    (dec / "decision_log.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")

    argv = sys.argv
    sys.argv = [
        "propose_playbook_evolution",
        "--repo-root",
        str(root),
        "--threshold",
        "3",
        "--dry-run",
    ]
    try:
        ppe.main()
    finally:
        sys.argv = argv

    out = capsys.readouterr().out
    assert "dry run lesson" in out
    assert not (root / "00_META" / "observability" / "PLAYBOOK_EVOLUTION_PROPOSALS.md").exists()
