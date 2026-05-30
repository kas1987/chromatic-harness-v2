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
from .policy import PolicyLoader

SpeedMode = Literal["speed", "balance", "low"]

# Routing-table provider id → providers.yaml registry key
_ROUTING_TO_POLICY: dict[str, str] = {
    "gemini": "gemini",
    "claude_api": "claude_api",
    "openai": "openai",
    "openrouter": "openrouter",
    "together_ai": "together_ai",
    "ollama_local": "ollama_local",
    "ollama_remote_desktop": "ollama_remote_desktop",
    "lmstudio": "lmstudio",
    "native_claude": "native_claude",
}

_LOCAL_ROUTING_PROVIDERS: frozenset[str] = frozenset(
    {"ollama_local", "ollama_remote_desktop", "lmstudio", "native_claude"}
)

# Cloud/broker ids in routing-table.yaml (blocked for P3–P5 per broker policy)
_CLOUD_ROUTING_PROVIDERS: frozenset[str] = frozenset(
    {"gemini", "openai", "claude_api", "openrouter", "together_ai"}
)

_PRIVACY_ORDER: dict[str, int] = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
    "P5": 5,
}


@dataclasses.dataclass(frozen=True)
class ProviderChoice:
    provider: str  # e.g. "ollama_local", "gemini"
    model: str | None  # e.g. "llama3.2:3b", "gemini-2.5-flash"
    tier: int  # 0–4, informational only
    reason: str


@dataclasses.dataclass(frozen=True)
class SelectionResult:
    ranked_choices: list[ProviderChoice]
    context_key: str  # e.g. "context_laptop"
    speed_mode: SpeedMode
    c_level: str


class ProviderSelector:
    """Reads routing-table.yaml and resolves providers."""

    DEFAULT_ROUTING_TABLE = (
        Path(__file__).resolve().parent.parent.parent
        / "09_DEPLOYMENT"
        / "config"
        / "routing"
        / "routing-table.yaml"
    )

    DEFAULT_PREFS = (
        Path.home() / ".claude" / "config" / "routing" / "user-preferences.yaml"
    )

    DEFAULT_OPENROUTER_MODELS = (
        Path(__file__).resolve().parent.parent.parent
        / "09_DEPLOYMENT"
        / "config"
        / "routing"
        / "openrouter-models.yaml"
    )

    def __init__(
        self,
        routing_table_path: Path | None = None,
        prefs_path: Path | None = None,
        openrouter_models_path: Path | None = None,
        policy_loader: PolicyLoader | None = None,
    ):
        self._table_path = routing_table_path or self.DEFAULT_ROUTING_TABLE
        self._prefs_path = prefs_path or self.DEFAULT_PREFS
        self._openrouter_models_path = (
            openrouter_models_path or self.DEFAULT_OPENROUTER_MODELS
        )
        self._policy_loader = policy_loader or PolicyLoader()
        self._table: dict = {}
        self._prefs: dict = {}
        self._providers_cfg: dict = {}
        self._openrouter_allowlist: set[str] = set()
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

        self._providers_cfg = self._policy_loader.providers()
        self._openrouter_allowlist = self._load_openrouter_allowlist()

    def _load_openrouter_allowlist(self) -> set[str]:
        path = self._openrouter_models_path
        if not path.exists():
            alt = (
                Path(__file__).resolve().parent.parent.parent
                / "config"
                / "routing"
                / "openrouter-models.yaml"
            )
            path = alt if alt.exists() else path
        if not path.exists():
            return set()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            str(m["id"])
            for m in data.get("models", [])
            if isinstance(m, dict) and m.get("id")
        }

    # ── Entry point ──────────────────────────────────────────────────────

    def select(
        self,
        complexity: ComplexityResult,
        context: RuntimeContext,
        speed_mode: SpeedMode | None = None,
        privacy_class: str = "P1",
    ) -> SelectionResult:
        """Return ranked provider choices for a task."""
        mode = self._resolve_speed_mode(speed_mode, context)
        ctx_key = self._resolve_context_key(context)
        c_level = complexity.level.upper()

        choices = self._lookup_routing_table(ctx_key, mode, c_level)
        filtered = self._filter_by_availability(choices, context)
        filtered = self._filter_by_privacy(filtered, privacy_class)
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
            return user_mode  # type: ignore[return-value]

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

    def _lookup_routing_table(
        self, ctx_key: str, mode: SpeedMode, c_level: str
    ) -> list[ProviderChoice]:
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
            choices.append(
                ProviderChoice(
                    provider=provider,
                    model=model,
                    tier=self._infer_tier(provider),
                    reason=f"routing table: {ctx_key}/{mode}/{c_level}",
                )
            )
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

    def _filter_by_availability(
        self, choices: list[ProviderChoice], context: RuntimeContext
    ) -> list[ProviderChoice]:
        filtered = []
        for c in choices:
            if c.provider == "ollama_local" and not context.ollama_local_reachable:
                continue
            if not context.internet_reachable and c.provider in _CLOUD_ROUTING_PROVIDERS:
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
            filtered.append(
                ProviderChoice(
                    provider="native_claude",
                    model=None,
                    tier=4,
                    reason="no reachable providers — fallback to native",
                )
            )
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

    # ── Privacy / OpenRouter broker policy ────────────────────────────────

    @staticmethod
    def _privacy_level(privacy_class: str) -> int:
        return _PRIVACY_ORDER.get(str(privacy_class).upper(), 4)

    def _provider_privacy_max(self, routing_provider: str) -> int:
        policy_name = _ROUTING_TO_POLICY.get(routing_provider, routing_provider)
        cfg = self._providers_cfg.get(policy_name, {})
        if "privacy_max" in cfg:
            return self._privacy_level(str(cfg["privacy_max"]))
        if routing_provider in _LOCAL_ROUTING_PROVIDERS:
            return self._privacy_level("P5")
        if routing_provider == "openrouter":
            return self._privacy_level("P1")
        return self._privacy_level("P2")

    def _filter_by_privacy(
        self, choices: list[ProviderChoice], privacy_class: str
    ) -> list[ProviderChoice]:
        """Enforce OPENROUTER_BROKER_POLICY + providers.yaml privacy_max."""
        task_level = self._privacy_level(privacy_class)
        filtered: list[ProviderChoice] = []
        for choice in choices:
            # P4/P5: hard block cloud/broker; local routes remain (no cloud egress)
            if task_level >= 4:
                if choice.provider in _CLOUD_ROUTING_PROVIDERS:
                    continue
                filtered.append(choice)
                continue
            if task_level >= 3 and choice.provider in _CLOUD_ROUTING_PROVIDERS:
                continue
            if task_level > self._provider_privacy_max(choice.provider):
                continue
            if choice.provider == "openrouter":
                if task_level > self._privacy_level("P1"):
                    continue
                if choice.model and self._openrouter_allowlist:
                    if choice.model not in self._openrouter_allowlist:
                        continue
                elif choice.model and not self._openrouter_allowlist:
                    continue
            filtered.append(choice)
        return filtered

    # ── Overrides ──────────────────────────────────────────────────────────

    def _apply_blocklist(self, choices: list[ProviderChoice]) -> list[ProviderChoice]:
        blocklist = self._prefs.get("provider_blocklist", [])
        return [c for c in choices if c.provider not in blocklist]

    def _apply_preference_override(
        self, choices: list[ProviderChoice]
    ) -> list[ProviderChoice]:
        pref = self._prefs.get("provider_preference")
        if not pref:
            return choices
        # Move preferred provider to front if present
        front = [c for c in choices if c.provider == pref]
        rest = [c for c in choices if c.provider != pref]
        return front + rest
