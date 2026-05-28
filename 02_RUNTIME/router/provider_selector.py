"""Provider selection: context + C-level + speed_mode → ranked provider list."""

from __future__ import annotations

import dataclasses
import os
import urllib.request
import yaml
from pathlib import Path
from typing import Literal

from .context_detector import ContextDetector, RuntimeContext
from .complexity_classifier import ComplexityResult

SpeedMode = Literal["speed", "balance", "low"]


@dataclasses.dataclass(frozen=True)
class ProviderChoice:
    provider: str           # e.g. "ollama_local", "gemini"
    model: str | None       # e.g. "llama3.2:3b", "gemini-2.5-flash"
    tier: int               # 0–4, informational only
    reason: str


@dataclasses.dataclass(frozen=True)
class SelectionResult:
    ranked_choices: list[ProviderChoice]
    context_key: str        # e.g. "context_laptop"
    speed_mode: SpeedMode
    c_level: str


class ProviderSelector:
    """Reads routing-table.yaml and resolves providers."""

    DEFAULT_ROUTING_TABLE = Path(__file__).resolve().parent.parent.parent / \
        "09_DEPLOYMENT" / "config" / "routing" / "routing-table.yaml"

    DEFAULT_PREFS = Path.home() / ".claude" / "config" / "routing" / "user-preferences.yaml"

    def __init__(
        self,
        routing_table_path: Path | None = None,
        prefs_path: Path | None = None,
    ):
        self._table_path = routing_table_path or self.DEFAULT_ROUTING_TABLE
        self._prefs_path = prefs_path or self.DEFAULT_PREFS
        self._table: dict = {}
        self._prefs: dict = {}
        self._load()

    def _load(self) -> None:
        if self._table_path.exists():
            with open(self._table_path, "r", encoding="utf-8") as f:
                self._table = yaml.safe_load(f) or {}
        else:
            self._table = {}

        if self._prefs_path.exists():
            with open(self._prefs_path, "r", encoding="utf-8") as f:
                self._prefs = yaml.safe_load(f) or {}
        else:
            self._prefs = {}

    # ── Entry point ──────────────────────────────────────────────────────

    def select(
        self,
        complexity: ComplexityResult,
        context: RuntimeContext,
        speed_mode: SpeedMode | None = None,
    ) -> SelectionResult:
        """Return ranked provider choices for a task."""
        mode = self._resolve_speed_mode(speed_mode, context)
        ctx_key = self._resolve_context_key(context)
        c_level = complexity.level.upper()

        choices = self._lookup_routing_table(ctx_key, mode, c_level)
        filtered = self._filter_by_availability(choices, context)
        filtered = self._apply_blocklist(filtered)
        filtered = self._apply_preference_override(filtered)

        return SelectionResult(
            ranked_choices=filtered,
            context_key=ctx_key,
            speed_mode=mode,
            c_level=c_level,
        )

    # ── Speed mode resolution ──────────────────────────────────────────────

    def _resolve_speed_mode(
        self, explicit: SpeedMode | None, context: RuntimeContext
    ) -> SpeedMode:
        if explicit:
            return explicit

        # Persistent user setting
        user_mode = self._prefs.get("speed_mode")
        if user_mode in ("speed", "balance", "low"):
            return user_mode

        # Auto-detect
        if not context.internet_reachable:
            return "low"
        if context.is_battery:
            return "low"
        return "balance"

    # ── Context key ───────────────────────────────────────────────────────

    @staticmethod
    def _resolve_context_key(context: RuntimeContext) -> str:
        if context.device_type == "desktop" and context.gpu_available:
            return "context_desktop"
        if context.device_type == "server":
            return "context_server"
        # Laptop: check if remote Ollama endpoints are reachable
        if context.remote_ollama_endpoints:
            # Simplified: if any endpoint configured, assume laptop_remote
            # In production, probe each endpoint first
            return "context_laptop_remote"
        return "context_laptop"

    # ── Routing table lookup ─────────────────────────────────────────────

    def _lookup_routing_table(self, ctx_key: str, mode: SpeedMode, c_level: str) -> list[ProviderChoice]:
        raw = self._table.get(ctx_key, {})
        mode_map = raw.get(mode, {})
        entries: list[str] = mode_map.get(c_level, [])

        choices: list[ProviderChoice] = []
        for entry in entries:
            # Parse "provider:model" syntax
            if ":" in entry:
                provider, model = entry.split(":", 1)
            else:
                provider, model = entry, None
            choices.append(ProviderChoice(
                provider=provider,
                model=model,
                tier=self._infer_tier(provider),
                reason=f"routing table: {ctx_key}/{mode}/{c_level}",
            ))
        return choices

    @staticmethod
    def _infer_tier(provider: str) -> int:
        """Rough tier mapping for informational display."""
        if "ollama" in provider:
            return 0
        if provider in ("lmstudio", "native_claude"):
            return 0
        if provider == "openai":
            return 2
        if provider == "gemini":
            return 3
        if provider == "claude_api":
            return 4
        if provider == "runpod":
            return 3
        return 4

    # ── Availability filtering ─────────────────────────────────────────

    def _filter_by_availability(self, choices: list[ProviderChoice], context: RuntimeContext) -> list[ProviderChoice]:
        filtered = []
        for c in choices:
            if c.provider == "ollama_local" and not context.ollama_local_reachable:
                continue
            if c.provider == "ollama_remote_desktop":
                # Simplified: probe first endpoint
                if not self._probe_remote_ollama(context.remote_ollama_endpoints):
                    continue
            if c.provider == "native_claude":
                # TODO: detect if we're inside a Claude session
                pass
            filtered.append(c)
        if not filtered:
            # Ultimate fallback
            filtered.append(ProviderChoice(
                provider="native_claude",
                model=None,
                tier=4,
                reason="no reachable providers — fallback to native",
            ))
        return filtered

    @staticmethod
    def _probe_remote_ollama(endpoints: list[dict]) -> bool:
        for ep in endpoints:
            if not ep.get("enabled", True):
                continue
            host = ep.get("host", "")
            port = ep.get("port", 11434)
            url = f"http://{host}:{port}/api/tags"
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                continue
        return False

    # ── Overrides ──────────────────────────────────────────────────────────

    def _apply_blocklist(self, choices: list[ProviderChoice]) -> list[ProviderChoice]:
        blocklist = self._prefs.get("provider_blocklist", [])
        return [c for c in choices if c.provider not in blocklist]

    def _apply_preference_override(self, choices: list[ProviderChoice]) -> list[ProviderChoice]:
        pref = self._prefs.get("provider_preference")
        if not pref:
            return choices
        # Move preferred provider to front if present
        front = [c for c in choices if c.provider == pref]
        rest = [c for c in choices if c.provider != pref]
        return front + rest
