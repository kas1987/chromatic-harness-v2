"""Request/response contracts for the Chromatic Router."""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from enum import Enum


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    PLANNING = "planning"
    CODING = "coding"
    REVIEW = "review"
    RESEARCH = "research"
    PERSONAL_CONTEXT = "personal_context"
    INTEGRATION_ACTION = "integration_action"


class PrivacyClass(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ConfidenceBand(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BLOCKED = "blocked"


class OutputType(str, Enum):
    TEXT = "text"
    JSON = "json"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


@dataclass
class RouteInput:
    messages: list[dict[str, Any]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteConstraints:
    privacy_class: PrivacyClass = PrivacyClass.P1
    max_cost_usd: float = 0.25
    max_latency_ms: int = 30000
    max_tokens: int = 8000
    allow_cloud: bool = True
    allow_broker: bool = True
    allow_openhuman: bool = False
    allow_tools: bool = False


@dataclass
class RouteConfidence:
    score: float = 0.0
    band: ConfidenceBand = ConfidenceBand.BLOCKED
    reason: str = ""


@dataclass
class RouteAudit:
    caller: str = "unknown"
    repo: str = ""
    human_gate_required: bool = False


@dataclass
class RouteRequest:
    request_id: str
    task_id: str
    task_type: TaskType
    objective: str
    input: RouteInput = field(default_factory=RouteInput)
    constraints: RouteConstraints = field(default_factory=RouteConstraints)
    confidence: RouteConfidence = field(default_factory=RouteConfidence)
    preferred_provider: str = "auto"
    fallback_chain: list[str] = field(default_factory=list)
    audit: RouteAudit = field(default_factory=RouteAudit)


@dataclass
class RouteUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class RouteOutput:
    type: OutputType = OutputType.TEXT
    content: str = ""


@dataclass
class RouteLogs:
    policy_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RouteResponse:
    request_id: str
    selected_provider: str = ""
    selected_model: str = ""
    route_reason: str = ""
    fallback_used: bool = False
    confidence_score: float = 0.0
    privacy_class: PrivacyClass = PrivacyClass.P0
    cost_estimate_usd: float = 0.0
    latency_ms: int = 0
    output: RouteOutput = field(default_factory=RouteOutput)
    usage: RouteUsage = field(default_factory=RouteUsage)
    logs: RouteLogs = field(default_factory=RouteLogs)
