"""Tests for Gap C: ship-idea completion check + ClosureMagnet enforcement."""

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.closure_magnet import ClosureMagnet  # noqa: E402
from magnets.ship_completion import check_ship_completion  # noqa: E402

_GOOD_LOG = (
    "[S8-LEAN] boot-tax=ok poll=ok inject=ok swappable=ok\n"
    "[S10-LIVE] wired=magnets/plugin.py:default_registry proof=trace_line_42\n"
)


class TestCheckShipCompletion:
    def test_not_applicable_when_no_evidence(self):
        r = check_ship_completion({"validation_passed": True})
        assert r["applicable"] is False
        assert r["complete"] is False

    def test_complete_via_log_plus_dod_flag(self):
        r = check_ship_completion({"ship_log": _GOOD_LOG, "dod_ok": True})
        assert r["applicable"] and r["complete"]
        assert r["missing"] == []

    def test_missing_live_when_proof_empty(self):
        log = "[S8-LEAN] boot-tax=ok\n[S10-LIVE] wired=foo.py proof=<>\n"
        r = check_ship_completion({"ship_log": log, "dod_ok": True})
        assert "S10-live" in r["missing"]
        assert not r["complete"]

    def test_missing_lean_when_bare_warn(self):
        log = "[S8-LEAN] boot-tax=WARN poll=ok\n" + _GOOD_LOG.splitlines()[1]
        r = check_ship_completion({"ship_log": log, "dod_ok": True})
        assert "S8-lean" in r["missing"]

    def test_justified_warn_passes_lean(self):
        log = "[S8-LEAN] boot-tax=WARN (justified: one-time) poll=ok\n"
        r = check_ship_completion({"ship_log": log})
        assert r["lean_ok"] is True

    def test_explicit_flags_override(self):
        r = check_ship_completion({"lean_ok": True, "live_ok": True, "dod_ok": True})
        assert r["complete"] is True

    def test_dod_required(self):
        r = check_ship_completion({"ship_log": _GOOD_LOG})
        assert "DoD" in r["missing"]

    def test_bead_scoping(self):
        log = (
            "[S8-LEAN] bead=B1 boot-tax=ok\n"
            "[S10-LIVE] bead=B1 wired=x.py proof=trace\n"
            "[S10-LIVE] bead=B2 wired=y.py proof=<>\n"
        )
        r = check_ship_completion({"ship_log": log, "bead_id": "B1", "dod_ok": True})
        assert r["complete"] is True


class TestClosureMagnetEnforcement:
    def test_legacy_close_when_no_ship_evidence(self):
        ev = ClosureMagnet().observe("M1", "closure", {"validation_passed": True})
        assert ev.recommended_action == "close_mission"

    def test_replan_when_ship_incomplete(self):
        ev = ClosureMagnet().observe(
            "M1",
            "closure",
            {"validation_passed": True, "ship_log": "[S8-LEAN] boot-tax=ok"},
        )
        assert ev.recommended_action == "replan"
        assert any("ship_incomplete" in e for e in ev.evidence)

    def test_close_when_ship_complete(self):
        ev = ClosureMagnet().observe(
            "M1",
            "closure",
            {"validation_passed": True, "ship_log": _GOOD_LOG, "dod_ok": True},
        )
        assert ev.recommended_action == "close_mission"

    def test_validation_failed_still_replan(self):
        ev = ClosureMagnet().observe("M1", "closure", {"validation_failed": True})
        assert ev.recommended_action == "replan"
