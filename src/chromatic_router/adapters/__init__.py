"""Provider adapters for Chromatic Router.

Stubs for missing adapters are provided here; they delegate to the canonical
implementation under 02_RUNTIME/router/adapters once available.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from router.adapters.base import BaseAdapter, AdapterHealth  # noqa: E402
from router.adapters.mock import MockAdapter  # noqa: E402
from router.adapters.openhuman_adapter import OpenHumanAdapter  # noqa: E402
from router.adapters.ollama_remote import OllamaRemoteAdapter  # noqa: E402
from router.adapters.ollama_adapter import OllamaAdapter  # noqa: E402
from router.adapters.lmstudio_adapter import LMStudioAdapter  # noqa: E402
from router.adapters.openai_adapter import OpenAIAdapter  # noqa: E402
from router.adapters.anthropic_adapter import AnthropicAdapter  # noqa: E402
from router.adapters.google_adapter import GoogleAdapter  # noqa: E402
from router.adapters.openrouter_adapter import OpenRouterAdapter  # noqa: E402
from router.adapters.featherless_adapter import FeatherlessAdapter  # noqa: E402

__all__ = [
    "BaseAdapter",
    "AdapterHealth",
    "MockAdapter",
    "OpenHumanAdapter",
    "OllamaRemoteAdapter",
    "OllamaAdapter",
    "LMStudioAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "OpenRouterAdapter",
    "FeatherlessAdapter",
]
