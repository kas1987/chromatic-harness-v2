"""Tests for extensible magnet plugin registry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import MagnetEvent
from magnets.magnet_orchestrator import MagnetOrchestrator
from magnets.plugin import MagnetPlugin, MagnetRegistry, default_registry
from magnets.plugins.secrets_plugin import SecretsSurfacePlugin


class EchoPlugin(MagnetPlugin):
    name = "echo_plugin"

    def observe(self, mission_id: str, inflection_point: str, signal: dict) -> MagnetEvent:
        return MagnetEvent(
            mission_id=mission_id,
            magnet_name=self.name,
            inflection_point=inflection_point,
            observed_signal=signal,
            evidence=[f"echo:{inflection_point}"],
        )


def test_register_custom_plugin():
    reg = MagnetRegistry()
    reg.register(EchoPlugin())
    event = reg.observe("m1", "echo_plugin", "tool_call", {"tool": "grep"})
    assert event.magnet_name == "echo_plugin"
    assert "echo:tool_call" in event.evidence


def test_default_registry_includes_plugins():
    reg = default_registry()
    names = reg.names()
    assert "confidence_magnet" in names
    assert "pyramid_check_plugin" in names
    assert "secrets_surface_plugin" in names


def test_orchestrator_register_plugin():
    orch = MagnetOrchestrator(MagnetRegistry())
    orch.register_plugin(EchoPlugin())
    assert "echo_plugin" in orch.registered_magnets()


def test_secrets_plugin_halts_on_hits():
    plugin = SecretsSurfacePlugin()
    event = plugin.observe("m1", "scan", {"secrets_detected": ["sk-abc"]})
    assert event.risk_delta > 0
    assert event.recommended_action == "halt"


def test_existing_orchestrator_tests_still_pass_names():
    orch = MagnetOrchestrator()
    assert "intent_magnet" in orch.registered_magnets()
