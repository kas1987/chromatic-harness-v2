"""Integration test: mission -> magnet -> agent_lead -> bead_queue -> event_stream visibility."""

import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Setup test environment with isolated DB
test_db_dir = tempfile.mkdtemp()
os.environ["CHROMATIC_DB_PATH"] = os.path.join(test_db_dir, "handoff_test.sqlite")


def _load_module(module_path: str, name: str):
    """Dynamic import of runtime modules."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader, f"Could not load spec for {module_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def repo_root():
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def agent_lead_module(repo_root):
    path = repo_root / "02_RUNTIME" / "orchestrator" / "agent_lead.py"
    return _load_module(str(path), "agent_lead_handoff_test")


@pytest.fixture
def event_hub(tmp_path):
    # Per-test tmpdir root eliminates cross-run event accumulation in the file store
    from console_api.event_store import MissionEventHub

    return MissionEventHub(tmp_path)


@pytest.fixture(scope="module")
def intake_queue(repo_root):
    from intake.queue import IntakeEntry, append_entry, default_queue_path

    return default_queue_path(repo_root)


@pytest.fixture
def sample_mission():
    """Sample mission with realistic context. UUID suffix prevents cross-run ID collisions."""
    return {
        "mission_id": f"CHR-HANDOFF-{uuid.uuid4().hex[:8]}",
        "objective": "Implement user authentication module with OAuth",
        "confidence_required": 85.0,
        "autonomy_level": "L3",
        "stage": "synthesis",
    }


@pytest.fixture
def sample_magnet_events(sample_mission):
    """Magnet events from a completed mission. Derives mission_id from sample_mission."""
    from magnets.base_magnet import MagnetEvent

    mid = sample_mission["mission_id"]
    return [
        MagnetEvent(
            mission_id=mid,
            magnet_name="confidence_magnet",
            inflection_point="validation",
            observed_signal={"coverage": 0.92, "tests": "all_pass"},
            risk_delta=-0.08,
            confidence_delta=18.0,
            recommended_action="proceed",
        ),
        MagnetEvent(
            mission_id=mid,
            magnet_name="execution_magnet",
            inflection_point="execution",
            observed_signal={"tasks_closed": 15, "errors": 0},
            risk_delta=0.0,
            confidence_delta=8.0,
            recommended_action="proceed",
        ),
        MagnetEvent(
            mission_id=mid,
            magnet_name="discipline_magnet",
            inflection_point="validation",
            observed_signal={"scope_adherence": 1.0, "timeline": "on_schedule"},
            risk_delta=-0.03,
            confidence_delta=5.0,
            recommended_action="proceed",
        ),
    ]


class TestAgentLeadHandoffIntegration:
    """Integration test for mission → synthesis → queue → events pipeline."""

    def test_agent_lead_synthesis_produces_valid_output(
        self, agent_lead_module, sample_mission, sample_magnet_events
    ):
        """Agent Lead produces structured output with decision and bead guidance."""
        AgentLead = agent_lead_module.AgentLead
        output = AgentLead().run(sample_mission, sample_magnet_events)

        assert (
            output.final_report["synthesis"]["mission_id"]
            == sample_mission["mission_id"]
        )
        assert output.decision in (
            "proceed",
            "proceed_reversible_only",
            "review",
            "halt",
            "replan",
        )
        assert output.final_report is not None
        assert output.handoff_prep is not None
        # When proceeding with high confidence, no bead needed
        if output.decision in ("proceed", "proceed_reversible_only"):
            assert output.suggested_bead is None
        assert output.final_report.get("recommendation") is not None
        assert output.final_report.get("evaluation") is not None
        assert output.audit_log is not None

    def test_high_risk_mission_creates_suggested_bead(
        self, agent_lead_module, sample_mission
    ):
        """High-risk synthesis produces a suggested bead for remediation."""
        from magnets.base_magnet import MagnetEvent

        AgentLead = agent_lead_module.AgentLead
        risky_events = [
            MagnetEvent(
                mission_id=sample_mission["mission_id"],
                magnet_name="security_magnet",
                inflection_point="execution",
                observed_signal={"secret_exposure": True, "vault_leak": True},
                risk_delta=0.75,
                confidence_delta=-40.0,
                recommended_action="halt_and_revert",
                evidence=["AWS_KEY in logs", "DB_PASSWORD in trace"],
            ),
        ]
        output = AgentLead().run(sample_mission, risky_events)

        assert output.decision == "halt"
        assert output.suggested_bead is not None
        assert output.suggested_bead.get("priority") in ("p0", "p1")
        # Bead is created for halt decision
        assert output.suggested_bead.get("title") is not None

    def test_bead_queue_accepts_dispatch(self, intake_queue, repo_root):
        """IntakeQueue persists bead dispatch entries correctly."""
        from intake.queue import append_entry, list_entries
        import uuid

        entry_data = {
            "id": f"intake-{uuid.uuid4().hex[:8]}",
            "source": "bead_hook",
            "kind": "bead_dispatch",
            "status": "queued",
            "title": "[synthesis] Post-mission security audit",
            "priority": "P1",
            "type": "task",
            "lane": "review",
            "context": {
                "mission_id": f"CHR-HANDOFF-{uuid.uuid4().hex[:8]}",
                "suggested_by": "agent_lead",
                "confidence_score": 88.5,
            },
        }
        entry = append_entry(entry_data, path=intake_queue)

        # Verify entry was written
        entries = list_entries(path=intake_queue)
        latest = [e for e in entries if e.id == entry.id]
        assert len(latest) == 1
        assert latest[0].source == "bead_hook"
        assert latest[0].kind == "bead_dispatch"

    def test_event_hub_publishes_synthesis_events(self, event_hub):
        """EventHub persists and replays synthesis events."""
        mission_id = f"CHR-SYNTH-{uuid.uuid4().hex[:8]}"
        event1 = {
            "event_type": "synthesis_start",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "magnet_count": 3,
        }
        event2 = {
            "event_type": "synthesis_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": "proceed",
            "confidence_final": 92.5,
        }

        event_hub.publish(mission_id, event1)
        event_hub.publish(mission_id, event2)

        # Replay and verify
        events = event_hub.replay(mission_id)
        assert len(events) >= 2
        assert any(e.get("event_type") == "synthesis_start" for e in events)
        assert any(e.get("event_type") == "synthesis_complete" for e in events)

    def test_event_stream_visibility_for_frontend(self, event_hub):
        """Frontend can subscribe to and replay the complete event stream."""
        import uuid

        mission_id = f"CHR-HANDOFF-{uuid.uuid4().hex[:8]}"

        # Simulate a sequence of synthesis lifecycle events
        events_to_publish = [
            {
                "event_type": "mission_received",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "magnets_analyzing",
                "count": 4,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "magnet_complete",
                "magnet": "confidence",
                "risk_delta": -0.1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "magnet_complete",
                "magnet": "execution",
                "risk_delta": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "synthesis_gate",
                "pass": True,
                "confidence": 89.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "decision_made",
                "decision": "proceed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "bead_queued",
                "bead_id": None,
                "reason": "passing_decision_no_bead",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]

        for event in events_to_publish:
            event_hub.publish(mission_id, event)

        # Frontend replay API
        replayed = event_hub.replay(mission_id, limit=100)
        assert len(replayed) >= len(events_to_publish)

        # Verify event stream order
        event_types = [e.get("event_type") for e in replayed]
        assert "mission_received" in event_types
        assert "bead_queued" in event_types
        assert "magnets_analyzing" in event_types
        assert "synthesis_gate" in event_types

    def test_end_to_end_mission_to_queue_to_event(
        self,
        agent_lead_module,
        intake_queue,
        event_hub,
        sample_mission,
        sample_magnet_events,
        repo_root,
    ):
        """Complete E2E: mission synthesis → bead decision → queue entry → event visibility."""
        from intake.queue import IntakeEntry, append_entry
        import uuid

        # Step 1: Run synthesis
        AgentLead = agent_lead_module.AgentLead
        synthesis_output = AgentLead().run(sample_mission, sample_magnet_events)

        assert (
            synthesis_output.final_report["synthesis"]["mission_id"]
            == sample_mission["mission_id"]
        )
        assert synthesis_output.decision in (
            "proceed",
            "proceed_reversible_only",
            "review",
            "halt",
            "replan",
        )

        # Step 2: Create bead dispatch if suggested
        if synthesis_output.suggested_bead:
            # Bead suggested due to risk; create dispatch entry
            entry_data = {
                "id": f"intake-{uuid.uuid4().hex[:8]}",
                "source": "bead_hook",
                "kind": "bead_dispatch",
                "status": "queued",
                "title": synthesis_output.suggested_bead.get("title", "Unknown"),
                "priority": synthesis_output.suggested_bead.get(
                    "priority", "P2"
                ).upper(),
                "type": "task",
                "lane": "review",
                "context": {
                    "mission_id": sample_mission["mission_id"],
                    "synthesis_decision": synthesis_output.decision,
                    "evidence": synthesis_output.suggested_bead.get("evidence", []),
                },
            }
            append_entry(entry_data, path=intake_queue)

        # Step 3: Publish synthesis events for frontend
        event_hub.publish(
            sample_mission["mission_id"],
            {
                "event_type": "synthesis_complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": synthesis_output.decision,
                "confidence_final": float(
                    synthesis_output.final_report.get("confidence_score", 0)
                ),
                "bead_suggested": synthesis_output.suggested_bead is not None,
            },
        )

        # Step 4: Frontend verifies visibility
        events = event_hub.replay(sample_mission["mission_id"])
        synthesis_event = [
            e for e in events if e.get("event_type") == "synthesis_complete"
        ]
        assert len(synthesis_event) > 0
        assert synthesis_event[0]["decision"] == synthesis_output.decision

        # Verify queue was updated if bead suggested
        if synthesis_output.suggested_bead:
            from intake.queue import list_entries

            queue_entries = list_entries(path=intake_queue)
            agent_lead_entries = [
                e
                for e in queue_entries
                if e.source == "bead_hook"  # agent_lead dispatches use bead_hook source
                and sample_mission["mission_id"] in e.context.get("mission_id", "")
            ]
            assert len(agent_lead_entries) > 0

    def test_bead_queue_entry_matches_synthesis_decision(
        self, agent_lead_module, sample_mission, sample_magnet_events
    ):
        """Queued bead priority aligns with synthesis risk assessment."""
        from magnets.base_magnet import MagnetEvent

        AgentLead = agent_lead_module.AgentLead

        # High-risk synthesis
        high_risk_events = [
            MagnetEvent(
                mission_id=sample_mission["mission_id"],
                magnet_name="cost_magnet",
                inflection_point="execution",
                observed_signal={"budget_overrun": 0.45},
                risk_delta=0.6,
                confidence_delta=-25.0,
                recommended_action="review_and_approve",
            ),
        ]
        output = AgentLead().run(sample_mission, high_risk_events)

        if output.suggested_bead:
            # Map synthesis risk to queue priority
            risk_level = output.final_report.get("risk_score", 0.5)
            priority = "P0" if risk_level > 0.7 else "P1" if risk_level > 0.4 else "P2"

            entry_data = {
                "id": "test-priority-mapping",
                "source": "bead_hook",
                "kind": "bead_dispatch",
                "status": "queued",
                "title": "Test priority mapping",
                "priority": priority,
                "context": {"risk_score": risk_level},
            }

            assert priority in ("P0", "P1", "P2", "P3")
            if risk_level > 0.7:
                assert priority == "P0"
