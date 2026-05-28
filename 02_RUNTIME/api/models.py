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
