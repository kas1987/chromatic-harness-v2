from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import Any, Optional

# Canonical mission-packet field names are confidence_score / required_output.
# These models also accept the pre-migration names (confidence_required /
# required_outputs) on input so already-persisted rows and legacy API callers
# keep deserializing during the migration window.
_CONF_ALIAS = AliasChoices("confidence_score", "confidence_required")
_OUT_ALIAS = AliasChoices("required_output", "required_outputs")


class CreateMissionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    objective: str
    agent_role: str = "agent_lead"
    autonomy_level: str = "L1"
    confidence_score: int = Field(75, validation_alias=_CONF_ALIAS)
    allowed_tools: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    required_output: list[str] = Field(default_factory=list, validation_alias=_OUT_ALIAS)


class MissionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mission_id: str
    objective: str
    agent_role: str
    autonomy_level: str
    confidence_score: int = Field(validation_alias=_CONF_ALIAS)
    allowed_tools: list[str]
    stop_conditions: list[str]
    required_output: list[str] = Field(validation_alias=_OUT_ALIAS)
    status: str
    magnets: list[str]


class CreateEventRequest(BaseModel):
    magnet_name: str
    inflection_point: str
    observed_signal: dict[str, Any]
    risk_delta: float = 0.0
    confidence_delta: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str = "none"


class MagnetEventResponse(BaseModel):
    event_id: str
    mission_id: str
    magnet_name: str
    inflection_point: str
    observed_signal: dict[str, Any]
    risk_delta: float
    confidence_delta: float
    evidence: list[str]
    recommended_action: str
    timestamp: str


class CreateBeadRequest(BaseModel):
    title: str
    objective: str
    priority: str = "p2"
    source: str = "magnet"
    mission_id: Optional[str] = None


class BeadResponse(BaseModel):
    bead_id: str
    title: str
    objective: str
    priority: str
    status: str
    source: str
    mission_id: Optional[str]
    created_at: str


class PromotionRecord(BaseModel):
    level: int
    date: str
    reason: str


class ViolationRecord(BaseModel):
    date: str
    violation_type: str


class RegisterAgentRequest(BaseModel):
    agent_id: str
    description: str = ""
    initial_level: int = Field(default=0, ge=0, le=5)


class AgentProfileResponse(BaseModel):
    agent_id: str
    description: str
    current_level: int
    total_executions: int
    successful_executions: int
    success_rate: float
    avg_confidence: float
    risk_score: float
    promotion_history: list[PromotionRecord]
    last_violation: Optional[ViolationRecord]
    created_at: str
    updated_at: str


class RecordExecutionRequest(BaseModel):
    success: bool
    confidence_score: float = Field(default=75.0, ge=0.0, le=100.0)
    risk_delta: float = 0.0


class PromoteAgentRequest(BaseModel):
    new_level: int = Field(ge=0, le=5)
    reason: str


class TrendPoint(BaseModel):
    timestamp: str
    value: float


class MagnetBreakdown(BaseModel):
    magnet_name: str
    event_count: int
    total_risk_delta: float
    total_confidence_delta: float


class ActionCount(BaseModel):
    action: str
    count: int


class MissionAnalyticsResponse(BaseModel):
    mission_id: str
    event_count: int
    duration_seconds: float
    confidence_trend: list[TrendPoint]
    risk_trend: list[TrendPoint]
    magnet_breakdown: list[MagnetBreakdown]
    top_actions: list[ActionCount]
    avg_risk_delta: float
    avg_confidence_delta: float


class AgentLeadResponse(BaseModel):
    mission_id: str
    decision: str
    composite_score: float
    final_report: dict[str, Any]
    pr_package: dict[str, Any]
    next_steps: dict[str, Any]
    audit_log: dict[str, Any]
    handoff_prep: dict[str, Any]
    suggested_bead: Optional[dict[str, Any]] = None
    bead_created: Optional[BeadResponse] = None


class UserRegisterRequest(BaseModel):
    username: str
    password: str  # pragma: allowlist secret  (field name, not a secret value)
    role: str = "executor"


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str  # pragma: allowlist secret  (field name, not a secret value)
    token_type: str = "bearer"
    user_id: str
    role: str
