"""Tests for MagnetOrchestrator pipeline."""

from magnets.base_magnet import MagnetEvent
from magnets.magnet_orchestrator import MagnetOrchestrator


class TestMagnetOrchestrator:
    def test_empty_events_yields_review(self):
        orch = MagnetOrchestrator()
        report = orch.process("CHR-TEST", [])
        assert report.collected_count == 0
        assert report.recommendation in ("review", "replan")
        assert "No magnet events" in report.feedback[0]

    def test_pipeline_stages_populated(self):
        orch = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="CHR-TEST",
                magnet_name="confidence_magnet",
                inflection_point="validation",
                observed_signal={"pass": True},
                risk_delta=-0.05,
                confidence_delta=10.0,
                recommended_action="proceed",
            ),
            MagnetEvent(
                mission_id="CHR-TEST",
                magnet_name="execution_magnet",
                inflection_point="execution",
                observed_signal={"tool": "bash"},
                risk_delta=0.1,
                confidence_delta=0.0,
                recommended_action="warn",
            ),
        ]
        report = orch.process("CHR-TEST", events)
        assert report.collected_count == 2
        assert len(report.normalized) == 2
        assert report.correlated["event_count"] == 2
        assert "confidence_magnet" in report.correlated["magnets_seen"]
        assert report.score > 0
        assert report.gold_artifact["recommendation"] == report.recommendation

    def test_halt_on_high_risk(self):
        orch = MagnetOrchestrator()
        events = [
            MagnetEvent(
                mission_id="CHR-TEST",
                magnet_name="security_magnet",
                inflection_point="execution",
                observed_signal={"injection": True},
                risk_delta=0.6,
                confidence_delta=-20.0,
                recommended_action="halt_and_revert",
                evidence=["prompt_injection"],
            ),
        ]
        report = orch.process("CHR-TEST", events)
        assert report.recommendation == "halt"
        assert report.correlated["halt_actions"] >= 1

    def test_intake_magnet_registered(self):
        orch = MagnetOrchestrator()
        assert "intake_magnet" in orch.registered_magnets()
        assert "closure_magnet" in orch.registered_magnets()
        assert "discipline_magnet" in orch.registered_magnets()

    def test_observe_intake_short_objective(self):
        orch = MagnetOrchestrator()
        event = orch.observe(
            "CHR-TEST", "intake_magnet", "intake", {"objective": "fix"}
        )
        assert event.recommended_action == "clarify_intent"
        assert event.risk_delta > 0
