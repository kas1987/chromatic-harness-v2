from pydantic import BaseModel, Field
from typing import Optional


class CreateMissionRequest(BaseModel):
    objective: str
    agent_role: str = "agent_lead"
    autonomy_level: str = "L1"
    confidence_required: float = 75.0
    allowed_tools: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)


class MissionResponse(BaseModel):
    mission_id: str
    objective: str
    agent_role: str
    autonomy_level: str
    confidence_required: float
    allowed_tools: list[str]
    stop_conditions: list[str]
    required_outputs: list[str]
    status: str
    magnets: list[str]


class CreateEventRequest(BaseModel):
    magnet_name: str
    inflection_point: str
    observed_signal: dict
    risk_delta: float = 0.0
    confidence_delta: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str = "none"


class MagnetEventResponse(BaseModel):
    event_id: str
    mission_id: str
    magnet_name: str
    inflection_point: str
    observed_signal: dict
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
