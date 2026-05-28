"""Chromatic Router — canonical package entrypoint.

This package re-exports the router implementation living under 02_RUNTIME/router
because Python cannot import digit-prefixed directories directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root so 'router' resolves to 02_RUNTIME/router
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Import the actual implementation from 02_RUNTIME/router
from router.router import ChromaticRouter  # noqa: E402
from router.contracts import (  # noqa: E402
    RouteRequest,
    RouteResponse,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteInput,
    RouteOutput,
    RouteUsage,
    RouteLogs,
    TaskType,
    PrivacyClass,
    ConfidenceBand,
    OutputType,
)
from router.policy import PolicyLoader  # noqa: E402
from router.confidence import ConfidenceGate  # noqa: E402
from router.privacy import PrivacyGate  # noqa: E402
from router.budget import BudgetGate  # noqa: E402
from router.observability import ObservabilityLogger  # noqa: E402
from router.adapters.base import BaseAdapter, AdapterHealth  # noqa: E402
from router.adapters.mock import MockAdapter  # noqa: E402
from router.adapters.openhuman_adapter import OpenHumanAdapter  # noqa: E402
from router.adapters.ollama_adapter import OllamaAdapter  # noqa: E402
from router.adapters.lmstudio_adapter import LMStudioAdapter  # noqa: E402
from router.adapters.openai_adapter import OpenAIAdapter  # noqa: E402
from router.adapters.anthropic_adapter import AnthropicAdapter  # noqa: E402
from router.adapters.google_adapter import GoogleAdapter  # noqa: E402
from router.adapters.openrouter_adapter import OpenRouterAdapter  # noqa: E402
from router.adapters.featherless_adapter import FeatherlessAdapter  # noqa: E402

__all__ = [
    "ChromaticRouter",
    "RouteRequest",
    "RouteResponse",
    "RouteConstraints",
    "RouteConfidence",
    "RouteAudit",
    "RouteInput",
    "RouteOutput",
    "RouteUsage",
    "RouteLogs",
    "TaskType",
    "PrivacyClass",
    "ConfidenceBand",
    "OutputType",
    "PolicyLoader",
    "ConfidenceGate",
    "PrivacyGate",
    "BudgetGate",
    "ObservabilityLogger",
    "BaseAdapter",
    "AdapterHealth",
    "MockAdapter",
    "OpenHumanAdapter",
    "OllamaAdapter",
    "LMStudioAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "OpenRouterAdapter",
    "FeatherlessAdapter",
]
