"""Extensible magnet plugin registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent


class MagnetPlugin(ABC):
    """Runtime-registerable magnet without editing MagnetOrchestrator."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique magnet id (e.g. security_surface_plugin)."""

    @abstractmethod
    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        """Handle one inflection-point signal."""

    def on_mission_start(
        self, mission_id: str, context: dict[str, Any] | None = None
    ) -> None:
        """Optional hook when a mission begins."""

    def on_mission_end(
        self, mission_id: str, context: dict[str, Any] | None = None
    ) -> None:
        """Optional hook when a mission completes."""


class BaseMagnetPluginAdapter(MagnetPlugin):
    """Wrap legacy BaseMagnet subclasses as plugins."""

    def __init__(self, magnet: BaseMagnet) -> None:
        self._magnet = magnet

    @property
    def name(self) -> str:
        return self._magnet.name

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        return self._magnet.observe(mission_id, inflection_point, signal)


class MagnetRegistry:
    """Central registry for built-in and custom magnets."""

    def __init__(self) -> None:
        self._plugins: dict[str, MagnetPlugin] = {}

    def register(self, plugin: MagnetPlugin, *, replace: bool = False) -> None:
        if plugin.name in self._plugins and not replace:
            raise ValueError(f"magnet already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def get(self, name: str) -> MagnetPlugin | None:
        return self._plugins.get(name)

    def names(self) -> list[str]:
        return sorted(self._plugins.keys())

    def observe(
        self,
        mission_id: str,
        magnet_name: str,
        inflection_point: str,
        signal: dict[str, Any],
        *,
        fallback: str = "intent_magnet",
    ) -> MagnetEvent:
        plugin = self._plugins.get(magnet_name) or self._plugins.get(fallback)
        if plugin is None:
            raise KeyError(f"no magnet registered: {magnet_name}")
        return plugin.observe(mission_id, inflection_point, signal)


def default_registry() -> MagnetRegistry:
    """Built-in magnets + repo plugins (pyramid, secrets surface)."""
    from .closure_magnet import ClosureMagnet
    from .confidence_magnet import ConfidenceMagnet
    from .cost_magnet import CostMagnet
    from .execution_magnet import ExecutionMagnet
    from .intake_magnet import IntakeMagnet
    from .intent_magnet import IntentMagnet
    from .memory_magnet import MemoryMagnet
    from .plugins.pyramid_plugin import PyramidCheckPlugin
    from .plugins.secrets_plugin import SecretsSurfacePlugin
    from .discipline_magnet import DisciplineMagnet
    from .quota_magnet import QuotaMagnet
    from .scope_magnet import ScopeMagnet
    from .security_magnet import SecurityMagnet
    from .validation_magnet import ValidationMagnet

    reg = MagnetRegistry()
    for magnet in (
        IntakeMagnet(),
        IntentMagnet(),
        ScopeMagnet(),
        DisciplineMagnet(),
        ExecutionMagnet(),
        CostMagnet(),
        ConfidenceMagnet(),
        ValidationMagnet(),
        MemoryMagnet(),
        SecurityMagnet(),
        QuotaMagnet(),
        ClosureMagnet(),
        PyramidCheckPlugin(),
        SecretsSurfacePlugin(),
    ):
        if isinstance(magnet, MagnetPlugin):
            reg.register(magnet)
        else:
            reg.register(BaseMagnetPluginAdapter(magnet))
    return reg
