"""Tests for Gap C closeout wiring: evaluate_ship_completion in session_closeout."""

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

_spec = importlib.util.spec_from_file_location("session_closeout", _REPO / "scripts" / "session_closeout.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)  # type: ignore

_COMPLETE = {
    "ship_log": ("[S8-LEAN] boot-tax=ok poll=ok inject=ok swappable=ok\n[S10-LIVE] wired=plugin.py proof=trace"),
    "dod_ok": True,
}
_INCOMPLETE = {"ship_log": "[S8-LEAN] boot-tax=ok"}  # no S10, no DoD


def test_no_evidence_blocks_nothing(tmp_path):
    r = sc.evaluate_ship_completion(["B1"], evidence_path=tmp_path / "absent.json")
    assert r["ok"] and r["block_close"] == [] and r["applicable"] is False


def test_flat_evidence_incomplete_blocks(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text(json.dumps(_INCOMPLETE), encoding="utf-8")
    r = sc.evaluate_ship_completion(["B1"], evidence_path=p)
    assert r["applicable"]
    assert any(v["bead_id"] == "B1" for v in r["block_close"])
    assert "S10-live" in r["block_close"][0]["missing"]


def test_complete_evidence_does_not_block(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text(json.dumps(_COMPLETE), encoding="utf-8")
    r = sc.evaluate_ship_completion(["B1"], evidence_path=p)
    assert r["block_close"] == []


def test_per_bead_keyed_evidence(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text(json.dumps({"B1": _COMPLETE, "B2": _INCOMPLETE}), encoding="utf-8")
    r = sc.evaluate_ship_completion(["B1", "B2"], evidence_path=p)
    blocked = {v["bead_id"] for v in r["block_close"]}
    assert blocked == {"B2"}


def test_malformed_evidence_fails_open(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text("{not json", encoding="utf-8")
    r = sc.evaluate_ship_completion(["B1"], evidence_path=p)
    assert r["ok"] is False and r["block_close"] == []
