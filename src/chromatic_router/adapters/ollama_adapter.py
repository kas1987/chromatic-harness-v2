"""Ollama local adapter — canonical entrypoint.

Re-exports the working OllamaRemoteAdapter from 02_RUNTIME/router/adapters
until a dedicated local-only adapter is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from router.adapters.ollama_remote import OllamaRemoteAdapter as _OllamaRemote  # noqa: E402


class OllamaAdapter(_OllamaRemote):
    """Canonical Ollama adapter; inherits OllamaRemoteAdapter behavior."""

    def __init__(self, cfg: dict | None = None):
        if cfg is None:
            cfg = {"enabled": True, "base_url": "http://localhost:11434"}
        # Normalize to the naming convention used in 02_RUNTIME
        super().__init__("ollama", cfg)
