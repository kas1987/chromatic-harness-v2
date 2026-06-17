"""Tests for the unified mission-packet validator (scripts/validate_mission_packet.py).

Covers both profiles (plan M1-M4, dispatch L0-L5), the L5 human-approval gate,
mode autonomy ceilings, and the shipped templates/examples under MISSIONS/.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "validate_mission_packet", REPO / "scripts" / "validate_mission_packet.py"
)
vmp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vmp)  # type: ignore[union-attr]


def _base_dispatch(**over):
    pkt = {
        "mission_id": "D-1",
        "objective": "do a thing",
        "agent_role": "agent_lead",
        "autonomy_level": "L2",
        "confidence_score": 80,
        "allowed_tools": ["read"],
        "stop_conditions": ["scope creep"],
        "required_output": ["summary"],
    }
    pkt.update(over)
    return pkt


# --- shipped templates/examples ------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "MISSIONS/templates/M1_BASIC_TEMPLATE.yaml",
        "MISSIONS/templates/M2_INTERMEDIATE_TEMPLATE.yaml",
        "MISSIONS/templates/M3_COMPLEX_TEMPLATE.yaml",
        "MISSIONS/templates/M4_ATOMIC_TEMPLATE.yaml",
        "MISSIONS/examples/M2_example_agent_log_ingestion.yaml",
        "MISSIONS/examples/dispatch_valid_L2_operator.json",
        "MISSIONS/examples/lifecycle_M2_plus_L1.yaml",
        "MISSIONS/examples/M3_example_review_daemon_recovery.yaml",
    ],
)
def test_shipped_packets_pass(rel):
    assert vmp.validate(vmp._load(str(REPO / rel))) == []


@pytest.mark.parametrize(
    "rel",
    [
        "MISSIONS/examples/_invalid_m3_missing_integration_points.yaml",
        "MISSIONS/examples/_invalid_dispatch_L5_unapproved.json",
        "MISSIONS/examples/_invalid_dispatch_mode_ceiling.json",
    ],
)
def test_shipped_negative_fixtures_fail(rel):
    assert vmp.validate(vmp._load(str(REPO / rel))) != []


# --- profile detection ---------------------------------------------------------


def test_packet_with_no_profile_is_rejected():
    pkt = {"mission_id": "x", "objective": "y", "confidence_score": 50, "stop_conditions": [], "required_output": []}
    errs = vmp.validate(pkt)
    assert any("neither" in e for e in errs)


def test_valid_dispatch_passes():
    assert vmp.validate(_base_dispatch()) == []


def test_dispatch_missing_agent_role_fails():
    pkt = _base_dispatch()
    del pkt["agent_role"]
    assert any("agent_role" in e for e in vmp.validate(pkt))


# --- L5 human-approval gate ----------------------------------------------------


def test_l5_without_human_approval_fails():
    pkt = _base_dispatch(autonomy_level="L5")
    assert any("human_approved" in e for e in vmp.validate(pkt))


def test_l5_with_human_approval_passes():
    pkt = _base_dispatch(autonomy_level="L5", metadata={"human_approved": True})
    assert vmp.validate(pkt) == []


# --- mode autonomy ceilings ----------------------------------------------------


def test_auditor_above_ceiling_fails():
    pkt = _base_dispatch(autonomy_level="L4", metadata={"mode": "auditor"})
    assert any("ceiling" in e for e in vmp.validate(pkt))


def test_operator_at_ceiling_passes():
    pkt = _base_dispatch(autonomy_level="L4", metadata={"mode": "operator"})
    assert vmp.validate(pkt) == []


# --- scalar checks -------------------------------------------------------------


def test_confidence_out_of_range_fails():
    assert any("confidence_score" in e for e in vmp.validate(_base_dispatch(confidence_score=130)))


def test_bad_risk_level_fails():
    pkt = _base_dispatch(risk_level="extreme")
    assert any("risk_level" in e for e in vmp.validate(pkt))
