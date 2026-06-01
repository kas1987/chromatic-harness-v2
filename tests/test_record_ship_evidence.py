"""Tests for the ship-evidence emitter (Gap C live feed)."""

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("record_ship_evidence", _REPO / "scripts" / "record_ship_evidence.py")
rse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rse)  # type: ignore


def test_record_creates_file(tmp_path):
    p = tmp_path / "ship.json"
    data = rse.record_evidence(p, bead_id="B1", lean_ok=True, live_ok=True, dod_ok=True)
    assert data["B1"] == {"lean_ok": True, "live_ok": True, "dod_ok": True}
    assert json.loads(p.read_text())["B1"]["live_ok"] is True


def test_merge_preserves_other_beads(tmp_path):
    p = tmp_path / "ship.json"
    rse.record_evidence(p, bead_id="B1", lean_ok=True)
    rse.record_evidence(p, bead_id="B2", dod_ok=True)
    data = json.loads(p.read_text())
    assert set(data) == {"B1", "B2"}


def test_partial_update_keeps_prior_fields(tmp_path):
    p = tmp_path / "ship.json"
    rse.record_evidence(p, bead_id="B1", lean_ok=True)
    rse.record_evidence(p, bead_id="B1", live_ok=True)
    assert json.loads(p.read_text())["B1"] == {"lean_ok": True, "live_ok": True}


def test_ship_log_stored(tmp_path):
    p = tmp_path / "ship.json"
    rse.record_evidence(p, bead_id="B1", ship_log="[S10-LIVE] wired=x proof=y")
    assert "S10-LIVE" in json.loads(p.read_text())["B1"]["ship_log"]


def test_clear_removes_entry(tmp_path):
    p = tmp_path / "ship.json"
    rse.record_evidence(p, bead_id="B1", lean_ok=True)
    rse.record_evidence(p, bead_id="B1", clear=True)
    assert "B1" not in json.loads(p.read_text())


def test_missing_bead_raises(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        rse.record_evidence(tmp_path / "x.json", bead_id="")


def test_corrupt_file_is_reset(tmp_path):
    p = tmp_path / "ship.json"
    p.write_text("{bad json", encoding="utf-8")
    data = rse.record_evidence(p, bead_id="B1", lean_ok=True)
    assert data == {"B1": {"lean_ok": True}}


def test_roundtrip_with_closeout_consumer(tmp_path):
    """End-to-end: emitted evidence is consumed correctly by evaluate_ship_completion."""
    import sys

    sys.path.insert(0, str(_REPO / "02_RUNTIME"))
    sc_spec = importlib.util.spec_from_file_location("session_closeout", _REPO / "scripts" / "session_closeout.py")
    sc = importlib.util.module_from_spec(sc_spec)
    sc_spec.loader.exec_module(sc)  # type: ignore

    if not hasattr(sc, "evaluate_ship_completion"):
        import pytest

        pytest.skip("consumer evaluate_ship_completion not present on this branch (#28)")

    p = tmp_path / "ship.json"
    rse.record_evidence(p, bead_id="B1", lean_ok=True, live_ok=True, dod_ok=True)
    rse.record_evidence(p, bead_id="B2", lean_ok=True)  # incomplete
    r = sc.evaluate_ship_completion(["B1", "B2"], evidence_path=p)
    blocked = {v["bead_id"] for v in r["block_close"]}
    assert blocked == {"B2"}
