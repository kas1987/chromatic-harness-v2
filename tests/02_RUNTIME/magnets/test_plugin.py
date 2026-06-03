"""Tests for magnets.plugin — MagnetPlugin, BaseMagnetPluginAdapter, MagnetRegistry, default_registry."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import pytest
from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.plugin import (
    BaseMagnetPluginAdapter,
    MagnetPlugin,
    MagnetRegistry,
    default_registry,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class _ConcretePlugin(MagnetPlugin):
    name = "test_concrete_plugin"

    def observe(self, mission_id, inflection_point, signal):
        return MagnetEvent(
            mission_id=mission_id,
            magnet_name=self.name,
            inflection_point=inflection_point,
            observed_signal=signal,
        )


class _AnotherPlugin(MagnetPlugin):
    name = "another_plugin"

    def observe(self, mission_id, inflection_point, signal):
        return MagnetEvent(
            mission_id=mission_id,
            magnet_name=self.name,
            inflection_point=inflection_point,
            observed_signal=signal,
        )


class _ConcreteBaseMagnet(BaseMagnet):
    name = "concrete_base"


# ---------------------------------------------------------------------------
# MagnetPlugin (ABC interface)
# ---------------------------------------------------------------------------


class TestMagnetPluginABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            MagnetPlugin()  # type: ignore[abstract]

    def test_concrete_subclass_is_instance(self):
        assert isinstance(_ConcretePlugin(), MagnetPlugin)

    def test_on_mission_start_default_noop(self):
        p = _ConcretePlugin()
        p.on_mission_start("m1", {})  # Should not raise

    def test_on_mission_end_default_noop(self):
        p = _ConcretePlugin()
        p.on_mission_end("m1", {})  # Should not raise

    def test_observe_returns_magnet_event(self):
        event = _ConcretePlugin().observe("m1", "intake", {"x": 1})
        assert isinstance(event, MagnetEvent)


# ---------------------------------------------------------------------------
# BaseMagnetPluginAdapter
# ---------------------------------------------------------------------------


class TestBaseMagnetPluginAdapter:
    def _adapter(self):
        return BaseMagnetPluginAdapter(_ConcreteBaseMagnet())

    def test_name_proxied(self):
        assert self._adapter().name == "concrete_base"

    def test_observe_delegates_to_inner_magnet(self):
        adapter = self._adapter()
        event = adapter.observe("m1", "intake", {"k": "v"})
        assert isinstance(event, MagnetEvent)
        assert event.magnet_name == "concrete_base"

    def test_is_magnet_plugin(self):
        assert isinstance(self._adapter(), MagnetPlugin)


# ---------------------------------------------------------------------------
# MagnetRegistry
# ---------------------------------------------------------------------------


class TestMagnetRegistry:
    def _reg(self) -> MagnetRegistry:
        r = MagnetRegistry()
        r.register(_ConcretePlugin())
        return r

    def test_register_and_get(self):
        reg = self._reg()
        plugin = reg.get("test_concrete_plugin")
        assert plugin is not None
        assert plugin.name == "test_concrete_plugin"

    def test_names_returns_sorted(self):
        reg = MagnetRegistry()
        reg.register(_ConcretePlugin())
        reg.register(_AnotherPlugin())
        assert reg.names() == ["another_plugin", "test_concrete_plugin"]

    def test_duplicate_registration_raises(self):
        reg = self._reg()
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_ConcretePlugin())

    def test_replace_allows_re_register(self):
        reg = self._reg()
        reg.register(_ConcretePlugin(), replace=True)  # should not raise

    def test_unregister_removes_plugin(self):
        reg = self._reg()
        reg.unregister("test_concrete_plugin")
        assert reg.get("test_concrete_plugin") is None

    def test_unregister_nonexistent_noop(self):
        reg = self._reg()
        reg.unregister("does_not_exist")  # should not raise

    def test_get_nonexistent_returns_none(self):
        reg = MagnetRegistry()
        assert reg.get("missing") is None

    def test_observe_delegates_to_plugin(self):
        reg = self._reg()
        event = reg.observe("m1", "test_concrete_plugin", "intake", {"data": 1})
        assert isinstance(event, MagnetEvent)
        assert event.magnet_name == "test_concrete_plugin"

    def test_observe_uses_fallback_when_missing(self):
        reg = MagnetRegistry()
        reg.register(_ConcretePlugin())
        # Request unknown magnet with fallback = test_concrete_plugin
        event = reg.observe("m1", "does_not_exist", "intake", {}, fallback="test_concrete_plugin")
        assert event.magnet_name == "test_concrete_plugin"

    def test_observe_raises_when_both_missing(self):
        reg = MagnetRegistry()
        with pytest.raises(KeyError):
            reg.observe("m1", "missing", "intake", {})

    def test_empty_names_list(self):
        reg = MagnetRegistry()
        assert reg.names() == []


# ---------------------------------------------------------------------------
# default_registry()
# ---------------------------------------------------------------------------

_EXPECTED_BUILT_IN = [
    "closure_magnet",
    "confidence_magnet",
    "context_pressure_magnet",
    "cost_magnet",
    "decision_magnet",
    "discipline_magnet",
    "dispatch_magnet",
    "execution_magnet",
    "intake_magnet",
    "intent_magnet",
    "memory_magnet",
    "plan_magnet",
    "pyramid_check_plugin",
    "quota_magnet",
    "scope_magnet",
    "secrets_surface_plugin",
    "security_magnet",
    "validation_magnet",
]


class TestDefaultRegistry:
    def test_all_built_in_magnets_registered(self):
        reg = default_registry()
        names = reg.names()
        for magnet in _EXPECTED_BUILT_IN:
            assert magnet in names, f"missing: {magnet}"

    def test_registry_has_at_least_18_magnets(self):
        reg = default_registry()
        assert len(reg.names()) >= 18

    def test_each_built_in_can_observe(self):
        reg = default_registry()
        for name in _EXPECTED_BUILT_IN:
            event = reg.observe("m1", name, "intake", {})
            assert isinstance(event, MagnetEvent), f"observe failed for {name}"

    def test_default_registry_is_independent(self):
        """Two calls return distinct registry objects."""
        r1 = default_registry()
        r2 = default_registry()
        r1.unregister("intake_magnet")
        assert "intake_magnet" not in r1.names()
        assert "intake_magnet" in r2.names()
