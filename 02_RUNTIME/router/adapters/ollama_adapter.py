"""Ollama local adapter — canonical entrypoint.

Re-exports the working OllamaRemoteAdapter from 02_RUNTIME/router/adapters
until a dedicated local-only adapter is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .ollama_remote import OllamaRemoteAdapter as _OllamaRemote


class OllamaAdapter(_OllamaRemote):
    """Canonical Ollama adapter; inherits OllamaRemoteAdapter behavior."""

    def __init__(self, cfg: dict | None = None):
        if cfg is None:
            cfg = {"enabled": True, "base_url": "http://localhost:11434"}
        # Normalize to the naming convention used in 02_RUNTIME
        super().__init__("ollama", cfg)
