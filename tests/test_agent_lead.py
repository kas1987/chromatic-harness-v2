"""Tests for Agent Lead synthesis pipeline."""

import importlib.util
import os
import sys

import pytest

from magnets.base_magnet import MagnetEvent


def _load_agent_lead():
    orch_dir = os.path.join(
        os.path.dirname(__file__), "..", "02_RUNTIME", "orchestrator"
    )
    path = os.path.join(orch_dir, "agent_lead.py")
    spec = importlib.util.spec_from_file_location("agent_lead_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def AgentLead():
    return _load_agent_lead().AgentLead


class TestAgentLead:
    def _sample_events(self):
        return [
            MagnetEvent(
                mission_id="CHR-LEAD-1",
                magnet_name="confidence_magnet",
                inflection_point="validation",
                observed_signal={"coverage": 0.9},
                risk_delta=-0.05,
                confidence_delta=15.0,
                recommended_action="proceed",
            ),
            MagnetEvent(
                mission_id="CHR-LEAD-1",
                magnet_name="validation_magnet",
                inflection_point="validation",
                observed_signal={"tests": "pass"},
                risk_delta=0.0,
                confidence_delta=5.0,
                recommended_action="proceed",
            ),
        ]

    def test_produces_all_output_documents(self, AgentLead):
        mission = {
            "mission_id": "CHR-LEAD-1",
            "objective": "Implement user authentication module",
            "confidence_required": 75.0,
            "autonomy_level": "L2",
        }
        output = AgentLead().run(mission, self._sample_events())
        assert output.final_report["executive_summary"]
        assert output.pr_package["title"]
        assert output.next_steps["actions"]
        assert output.audit_log["mission_id"] == "CHR-LEAD-1"
        assert output.handoff_prep["directive_summary"]
        assert output.decision in (
            "proceed",
            "proceed_reversible_only",
            "replan",
            "review",
            "halt",
        )

    def test_high_risk_suggests_bead(self, AgentLead):
        mission = {
            "mission_id": "CHR-RISK",
            "objective": "Deploy production hotfix",
            "confidence_required": 90.0,
        }
        events = [
            MagnetEvent(
                mission_id="CHR-RISK",
                magnet_name="security_magnet",
                inflection_point="execution",
                observed_signal={"secret_leak": True},
                risk_delta=0.7,
                confidence_delta=-30.0,
                recommended_action="halt_and_revert",
                evidence=["secret_detected"],
            ),
        ]
        output = AgentLead().run(mission, events)
        assert output.decision == "halt"
        assert output.suggested_bead is not None
        assert output.suggested_bead["priority"] == "p0"

    def test_proceeding_mission_no_bead(self, AgentLead):
        mission = {
            "mission_id": "CHR-OK",
            "objective": "Add logging to router",
            "confidence_required": 60.0,
        }
        output = AgentLead().run(mission, self._sample_events())
        if output.decision in ("proceed", "proceed_reversible_only"):
            assert output.suggested_bead is None
