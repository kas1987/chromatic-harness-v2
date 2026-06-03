"""Pydantic model validation tests for 02_RUNTIME/api/models.py.

Covers:
- Required field enforcement
- Optional / default values
- Type coercion (int, float, str, list)
- Field constraints (ge/le)
- Serialization / deserialization round-trips
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# conftest already puts 02_RUNTIME/api on sys.path
from models import (
    ActionCount,
    AgentLeadResponse,
    AgentProfileResponse,
    BeadResponse,
    CreateBeadRequest,
    CreateEventRequest,
    CreateMissionRequest,
    MagnetBreakdown,
    MagnetEventResponse,
    MissionAnalyticsResponse,
    MissionResponse,
    PromotionRecord,
    PromoteAgentRequest,
    RecordExecutionRequest,
    RegisterAgentRequest,
    TokenResponse,
    TrendPoint,
    UserRegisterRequest,
    UserResponse,
    ViolationRecord,
)


# ---------------------------------------------------------------------------
# CreateMissionRequest
# ---------------------------------------------------------------------------


class TestCreateMissionRequest:
    def test_requires_objective(self) -> None:
        with pytest.raises(ValidationError):
            CreateMissionRequest()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        req = CreateMissionRequest(objective="do something")
        assert req.agent_role == "agent_lead"
        assert req.autonomy_level == "L1"
        assert req.confidence_required == 75.0
        assert req.allowed_tools == []
        assert req.stop_conditions == []
        assert req.required_outputs == []

    def test_custom_values(self) -> None:
        req = CreateMissionRequest(
            objective="x",
            agent_role="specialist",
            autonomy_level="L4",
            confidence_required=95.0,
            allowed_tools=["bash"],
            stop_conditions=["done"],
            required_outputs=["report"],
        )
        assert req.agent_role == "specialist"
        assert req.allowed_tools == ["bash"]

    def test_round_trip(self) -> None:
        req = CreateMissionRequest(objective="round-trip")
        restored = CreateMissionRequest(**req.model_dump())
        assert restored == req


# ---------------------------------------------------------------------------
# MissionResponse
# ---------------------------------------------------------------------------


class TestMissionResponse:
    def _valid(self) -> dict:
        return {
            "mission_id": "CHR-ABCD1234",
            "objective": "test",
            "agent_role": "agent_lead",
            "autonomy_level": "L1",
            "confidence_required": 75.0,
            "allowed_tools": [],
            "stop_conditions": [],
            "required_outputs": [],
            "status": "dispatched",
            "magnets": ["m1"],
        }

    def test_valid(self) -> None:
        r = MissionResponse(**self._valid())
        assert r.mission_id == "CHR-ABCD1234"

    def test_missing_mission_id_raises(self) -> None:
        d = self._valid()
        del d["mission_id"]
        with pytest.raises(ValidationError):
            MissionResponse(**d)

    def test_magnets_defaults_to_list(self) -> None:
        d = self._valid()
        assert isinstance(MissionResponse(**d).magnets, list)


# ---------------------------------------------------------------------------
# CreateEventRequest
# ---------------------------------------------------------------------------


class TestCreateEventRequest:
    def test_requires_magnet_name(self) -> None:
        with pytest.raises(ValidationError):
            CreateEventRequest(
                inflection_point="start",
                observed_signal={},
            )  # type: ignore[call-arg]

    def test_requires_inflection_point(self) -> None:
        with pytest.raises(ValidationError):
            CreateEventRequest(
                magnet_name="m",
                observed_signal={},
            )  # type: ignore[call-arg]

    def test_requires_observed_signal(self) -> None:
        with pytest.raises(ValidationError):
            CreateEventRequest(
                magnet_name="m",
                inflection_point="p",
            )  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        req = CreateEventRequest(
            magnet_name="m",
            inflection_point="p",
            observed_signal={},
        )
        assert req.risk_delta == 0.0
        assert req.confidence_delta == 0.0
        assert req.evidence == []
        assert req.recommended_action == "none"

    def test_float_coercion(self) -> None:
        req = CreateEventRequest(
            magnet_name="m",
            inflection_point="p",
            observed_signal={},
            risk_delta=1,  # int → float
        )
        assert isinstance(req.risk_delta, float)


# ---------------------------------------------------------------------------
# MagnetEventResponse
# ---------------------------------------------------------------------------


class TestMagnetEventResponse:
    def _valid(self) -> dict:
        return {
            "event_id": "ev-1",
            "mission_id": "CHR-ABC",
            "magnet_name": "test",
            "inflection_point": "p1",
            "observed_signal": {"a": 1},
            "risk_delta": 0.1,
            "confidence_delta": 2.0,
            "evidence": ["e1"],
            "recommended_action": "proceed",
            "timestamp": "2024-01-01T00:00:00Z",
        }

    def test_valid(self) -> None:
        r = MagnetEventResponse(**self._valid())
        assert r.event_id == "ev-1"

    def test_round_trip(self) -> None:
        r = MagnetEventResponse(**self._valid())
        assert MagnetEventResponse(**r.model_dump()) == r


# ---------------------------------------------------------------------------
# CreateBeadRequest
# ---------------------------------------------------------------------------


class TestCreateBeadRequest:
    def test_requires_title_and_objective(self) -> None:
        with pytest.raises(ValidationError):
            CreateBeadRequest(objective="x")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            CreateBeadRequest(title="x")  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        req = CreateBeadRequest(title="t", objective="o")
        assert req.priority == "p2"
        assert req.source == "magnet"
        assert req.mission_id is None

    def test_optional_mission_id(self) -> None:
        req = CreateBeadRequest(title="t", objective="o", mission_id="CHR-X")
        assert req.mission_id == "CHR-X"


# ---------------------------------------------------------------------------
# BeadResponse
# ---------------------------------------------------------------------------


class TestBeadResponse:
    def _valid(self) -> dict:
        return {
            "bead_id": "BEAD-12345678",
            "title": "Fix bug",
            "objective": "Resolve the issue",
            "priority": "p1",
            "status": "created",
            "source": "magnet",
            "mission_id": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

    def test_valid(self) -> None:
        r = BeadResponse(**self._valid())
        assert r.bead_id == "BEAD-12345678"

    def test_null_mission_id_allowed(self) -> None:
        r = BeadResponse(**self._valid())
        assert r.mission_id is None

    def test_round_trip(self) -> None:
        r = BeadResponse(**self._valid())
        assert BeadResponse(**r.model_dump()) == r


# ---------------------------------------------------------------------------
# RegisterAgentRequest
# ---------------------------------------------------------------------------


class TestRegisterAgentRequest:
    def test_requires_agent_id(self) -> None:
        with pytest.raises(ValidationError):
            RegisterAgentRequest()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        req = RegisterAgentRequest(agent_id="a1")
        assert req.description == ""
        assert req.initial_level == 0

    def test_initial_level_constraint_ge0(self) -> None:
        with pytest.raises(ValidationError):
            RegisterAgentRequest(agent_id="a", initial_level=-1)

    def test_initial_level_constraint_le5(self) -> None:
        with pytest.raises(ValidationError):
            RegisterAgentRequest(agent_id="a", initial_level=6)

    def test_boundary_level_0(self) -> None:
        req = RegisterAgentRequest(agent_id="a", initial_level=0)
        assert req.initial_level == 0

    def test_boundary_level_5(self) -> None:
        req = RegisterAgentRequest(agent_id="a", initial_level=5)
        assert req.initial_level == 5


# ---------------------------------------------------------------------------
# AgentProfileResponse
# ---------------------------------------------------------------------------


class TestAgentProfileResponse:
    def _valid(self) -> dict:
        return {
            "agent_id": "a1",
            "description": "test",
            "current_level": 0,
            "total_executions": 0,
            "successful_executions": 0,
            "success_rate": 0.0,
            "avg_confidence": 0.0,
            "risk_score": 0.0,
            "promotion_history": [],
            "last_violation": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

    def test_valid(self) -> None:
        r = AgentProfileResponse(**self._valid())
        assert r.agent_id == "a1"

    def test_null_last_violation(self) -> None:
        r = AgentProfileResponse(**self._valid())
        assert r.last_violation is None

    def test_promotion_history_items(self) -> None:
        d = self._valid()
        d["promotion_history"] = [{"level": 1, "date": "2024-01-01", "reason": "ok"}]
        r = AgentProfileResponse(**d)
        assert r.promotion_history[0].level == 1

    def test_violation_record(self) -> None:
        d = self._valid()
        d["last_violation"] = {"date": "2024-01-01", "violation_type": "overreach"}
        r = AgentProfileResponse(**d)
        assert r.last_violation.violation_type == "overreach"


# ---------------------------------------------------------------------------
# RecordExecutionRequest
# ---------------------------------------------------------------------------


class TestRecordExecutionRequest:
    def test_requires_success(self) -> None:
        with pytest.raises(ValidationError):
            RecordExecutionRequest()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        req = RecordExecutionRequest(success=True)
        assert req.confidence_score == 75.0
        assert req.risk_delta == 0.0

    def test_confidence_ge0(self) -> None:
        with pytest.raises(ValidationError):
            RecordExecutionRequest(success=True, confidence_score=-0.1)

    def test_confidence_le100(self) -> None:
        with pytest.raises(ValidationError):
            RecordExecutionRequest(success=True, confidence_score=100.1)

    def test_boundary_confidence_0(self) -> None:
        req = RecordExecutionRequest(success=True, confidence_score=0.0)
        assert req.confidence_score == 0.0

    def test_boundary_confidence_100(self) -> None:
        req = RecordExecutionRequest(success=True, confidence_score=100.0)
        assert req.confidence_score == 100.0


# ---------------------------------------------------------------------------
# PromoteAgentRequest
# ---------------------------------------------------------------------------


class TestPromoteAgentRequest:
    def test_requires_new_level_and_reason(self) -> None:
        with pytest.raises(ValidationError):
            PromoteAgentRequest(reason="x")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            PromoteAgentRequest(new_level=1)  # type: ignore[call-arg]

    def test_level_ge0(self) -> None:
        with pytest.raises(ValidationError):
            PromoteAgentRequest(new_level=-1, reason="x")

    def test_level_le5(self) -> None:
        with pytest.raises(ValidationError):
            PromoteAgentRequest(new_level=6, reason="x")

    def test_valid(self) -> None:
        req = PromoteAgentRequest(new_level=3, reason="earned")
        assert req.new_level == 3
        assert req.reason == "earned"


# ---------------------------------------------------------------------------
# TrendPoint / MagnetBreakdown / ActionCount
# ---------------------------------------------------------------------------


class TestAnalyticsSubmodels:
    def test_trend_point(self) -> None:
        tp = TrendPoint(timestamp="2024-01-01", value=1.5)
        assert tp.value == 1.5

    def test_magnet_breakdown(self) -> None:
        mb = MagnetBreakdown(
            magnet_name="m",
            event_count=3,
            total_risk_delta=0.15,
            total_confidence_delta=6.0,
        )
        assert mb.event_count == 3

    def test_action_count(self) -> None:
        ac = ActionCount(action="proceed", count=5)
        assert ac.count == 5


# ---------------------------------------------------------------------------
# MissionAnalyticsResponse
# ---------------------------------------------------------------------------


class TestMissionAnalyticsResponse:
    def _valid(self) -> dict:
        return {
            "mission_id": "CHR-X",
            "event_count": 0,
            "duration_seconds": 0.0,
            "confidence_trend": [],
            "risk_trend": [],
            "magnet_breakdown": [],
            "top_actions": [],
            "avg_risk_delta": 0.0,
            "avg_confidence_delta": 0.0,
        }

    def test_valid(self) -> None:
        r = MissionAnalyticsResponse(**self._valid())
        assert r.event_count == 0

    def test_with_nested_items(self) -> None:
        d = self._valid()
        d["confidence_trend"] = [{"timestamp": "2024-01-01", "value": 1.0}]
        d["magnet_breakdown"] = [
            {
                "magnet_name": "m",
                "event_count": 1,
                "total_risk_delta": 0.1,
                "total_confidence_delta": 1.0,
            }
        ]
        r = MissionAnalyticsResponse(**d)
        assert r.confidence_trend[0].value == 1.0
        assert r.magnet_breakdown[0].magnet_name == "m"


# ---------------------------------------------------------------------------
# AgentLeadResponse
# ---------------------------------------------------------------------------


class TestAgentLeadResponse:
    def _valid(self) -> dict:
        return {
            "mission_id": "CHR-X",
            "decision": "proceed",
            "composite_score": 82.5,
            "final_report": {"summary": "ok"},
            "pr_package": {},
            "next_steps": {},
            "audit_log": {},
            "handoff_prep": {},
        }

    def test_valid(self) -> None:
        r = AgentLeadResponse(**self._valid())
        assert r.decision == "proceed"

    def test_optional_bead_fields_none(self) -> None:
        r = AgentLeadResponse(**self._valid())
        assert r.suggested_bead is None
        assert r.bead_created is None


# ---------------------------------------------------------------------------
# UserRegisterRequest
# ---------------------------------------------------------------------------


class TestUserRegisterRequest:
    def test_requires_username_and_password(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(password="pw")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            UserRegisterRequest(username="u")  # type: ignore[call-arg]

    def test_default_role(self) -> None:
        req = UserRegisterRequest(username="u", password="p")
        assert req.role == "executor"

    def test_custom_role(self) -> None:
        req = UserRegisterRequest(username="u", password="p", role="admin")
        assert req.role == "admin"


# ---------------------------------------------------------------------------
# UserResponse / TokenResponse
# ---------------------------------------------------------------------------


class TestUserResponse:
    def test_valid(self) -> None:
        r = UserResponse(
            user_id="uid-1",
            username="alice",
            role="executor",
            created_at="2024-01-01",
        )
        assert r.username == "alice"

    def test_round_trip(self) -> None:
        r = UserResponse(
            user_id="uid-1",
            username="alice",
            role="executor",
            created_at="2024-01-01",
        )
        assert UserResponse(**r.model_dump()) == r


class TestTokenResponse:
    def test_defaults(self) -> None:
        r = TokenResponse(access_token="tok", user_id="uid", role="executor")
        assert r.token_type == "bearer"

    def test_round_trip(self) -> None:
        r = TokenResponse(access_token="tok", user_id="uid", role="executor")
        assert TokenResponse(**r.model_dump()) == r


# ---------------------------------------------------------------------------
# PromotionRecord / ViolationRecord
# ---------------------------------------------------------------------------


class TestAuxiliaryRecords:
    def test_promotion_record(self) -> None:
        pr = PromotionRecord(level=2, date="2024-01-01", reason="promoted")
        assert pr.level == 2

    def test_violation_record(self) -> None:
        vr = ViolationRecord(date="2024-01-01", violation_type="overreach")
        assert vr.violation_type == "overreach"
