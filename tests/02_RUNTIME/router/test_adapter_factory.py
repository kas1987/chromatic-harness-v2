"""Unit tests for router.adapters.adapter_factory.build().

# DEFICIENCIES NOTED
#
# 1. The factory silently skips unknown providers (by design), which means
#    typos in providers.yaml or providers configs produce no error and no
#    adapter — callers must check the returned dict themselves.
#
# 2. _instantiate() has no error handling: if a registry entry points to a
#    bad module path or wrong class name, ImportError / AttributeError
#    propagates uncaught from build().
#
# 3. There is no public API to introspect which providers were skipped; the
#    caller gets back a plain dict and has no diff against what was requested.
#
# 4. The registry lookup is done fresh on every build() call (no caching),
#    so a malformed YAML causes a hard failure even for unrelated providers.
#
# 5. Prefix matching iterates in dict-insertion order (CPython 3.7+), but
#    the code relies on that ordering being stable; no explicit priority
#    mechanism exists if two prefixes both match a name.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import router.adapters.adapter_factory as factory_mod
from router.adapters.adapter_factory import _instantiate, _load_registry, build
from router.adapters.base import BaseAdapter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGISTRY_PATH = Path(__file__).parents[4] / "02_RUNTIME" / "router" / "adapters" / "adapters.yaml"

# All exact adapter names from adapters.yaml
EXACT_PROVIDERS = [
    "openhuman",
    "lmstudio",
    "openai",
    "anthropic",
    "google",
    "openrouter",
    "featherless",
    "kimi",
    "prism-orchestrator",
    "native_claude",
]

# All prefix groups that live in adapters.yaml
PREFIX_PROVIDERS = [
    "ollama",
    "ollama_local",
    "ollama_remote_desktop",
    "ollama_anything_else",
]


def _stub_adapter_cls(name: str = "stub") -> type:
    """Return a minimal concrete BaseAdapter subclass."""

    class _Stub(BaseAdapter):
        def __init__(self, cfg: dict):
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    _Stub.__name__ = f"Stub_{name}"
    return _Stub


def _stub_adapter_cls_with_name(klass_name: str = "stub") -> type:
    """Return a concrete BaseAdapter that takes (name, cfg) — for pass_name entries."""

    class _StubName(BaseAdapter):
        def __init__(self, name: str, cfg: dict):
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    _StubName.__name__ = klass_name
    return _StubName


def _minimal_registry(
    *,
    provider: str,
    module: str = "fake_mod",
    cls: str = "FakeCls",
    pass_name: bool = False,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"module": module, "class": cls}
    if pass_name:
        entry["pass_name"] = True
    return {"version": "1.0", "adapters": {provider: entry}, "prefixes": {}}


def _minimal_prefix_registry(
    *,
    prefix: str,
    module: str = "fake_mod",
    cls: str = "FakeCls",
    pass_name: bool = False,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"module": module, "class": cls}
    if pass_name:
        entry["pass_name"] = True
    return {"version": "1.0", "adapters": {}, "prefixes": {prefix: entry}}


# ---------------------------------------------------------------------------
# _load_registry
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    def test_loads_real_yaml(self):
        data = _load_registry(_REGISTRY_PATH)
        assert "adapters" in data
        assert "prefixes" in data

    def test_adapters_is_dict(self):
        data = _load_registry(_REGISTRY_PATH)
        assert isinstance(data["adapters"], dict)

    def test_prefixes_is_dict(self):
        data = _load_registry(_REGISTRY_PATH)
        assert isinstance(data["prefixes"], dict)

    def test_raises_on_missing_pyyaml(self):
        with patch.dict("sys.modules", {"yaml": None}):
            with pytest.raises(ImportError, match="pyyaml"):
                _load_registry(_REGISTRY_PATH)

    def test_raises_on_nonexistent_path(self, tmp_path):
        with pytest.raises(Exception):
            _load_registry(tmp_path / "does_not_exist.yaml")


# ---------------------------------------------------------------------------
# _instantiate
# ---------------------------------------------------------------------------


class TestInstantiate:
    def test_calls_cls_with_cfg_only(self):
        StubCls = _stub_adapter_cls("my_provider")
        fake_module = MagicMock()
        fake_module.StubCls = StubCls
        entry = {"module": "fake_mod", "class": "StubCls"}
        cfg = {"enabled": True, "key": "val"}
        with patch("importlib.import_module", return_value=fake_module):
            instance = _instantiate(entry, "my_provider", cfg)
        assert isinstance(instance, StubCls)

    def test_calls_cls_with_name_when_pass_name_true(self):
        calls: list[tuple] = []

        class NamedStub(BaseAdapter):
            def __init__(self, name: str, cfg: dict):
                calls.append((name, cfg))
                super().__init__(name, cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        fake_module = MagicMock()
        fake_module.NamedStub = NamedStub
        entry = {"module": "fake_mod", "class": "NamedStub", "pass_name": True}
        with patch("importlib.import_module", return_value=fake_module):
            _instantiate(entry, "ollama_remote", {"host": "10.0.0.1"})
        assert calls == [("ollama_remote", {"host": "10.0.0.1"})]

    def test_does_not_pass_name_when_pass_name_false(self):
        calls: list = []

        class NoCfgStub(BaseAdapter):
            def __init__(self, cfg: dict):
                calls.append(cfg)
                super().__init__("stub", cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        fake_module = MagicMock()
        fake_module.NoCfgStub = NoCfgStub
        entry = {"module": "fake_mod", "class": "NoCfgStub", "pass_name": False}
        cfg = {"model": "gpt-4o"}
        with patch("importlib.import_module", return_value=fake_module):
            _instantiate(entry, "openai", cfg)
        assert calls == [cfg]

    def test_propagates_import_error(self):
        entry = {"module": "no_such_module_xyz", "class": "Foo"}
        with pytest.raises(ModuleNotFoundError):
            _instantiate(entry, "bad_provider", {})

    def test_propagates_attribute_error_for_missing_class(self):
        import sys

        import types

        dummy_module = types.ModuleType("dummy_mod_abc")
        with patch.dict("sys.modules", {"dummy_mod_abc": dummy_module}):
            entry = {"module": "dummy_mod_abc", "class": "NonExistentClass"}
            with pytest.raises(AttributeError):
                _instantiate(entry, "provider", {})


# ---------------------------------------------------------------------------
# build() — empty / unknown providers
# ---------------------------------------------------------------------------


class TestBuildEmpty:
    def test_empty_providers_dict_returns_empty_result(self):
        result = build({}, registry_path=_REGISTRY_PATH)
        assert result == {}

    def test_unknown_provider_silently_skipped(self):
        result = build({"no_such_provider_xyz": {}}, registry_path=_REGISTRY_PATH)
        assert "no_such_provider_xyz" not in result
        assert result == {}

    def test_multiple_unknown_providers_all_skipped(self):
        providers = {"x1": {}, "x2": {}, "x3": {}}
        result = build(providers, registry_path=_REGISTRY_PATH)
        assert result == {}

    def test_mixed_known_unknown_only_known_built(self, tmp_path):
        """Only the known provider 'myp' is in the registry; unknowns are skipped."""
        StubCls = _stub_adapter_cls("myp")
        fake_module = MagicMock()
        fake_module.FakeCls = StubCls

        yaml_content = 'version: "1.0"\nadapters:\n  myp:\n    module: fake_mod\n    class: FakeCls\nprefixes: {}\n'
        reg = tmp_path / "adapters.yaml"
        reg.write_text(yaml_content)

        with patch("importlib.import_module", return_value=fake_module):
            result = build({"myp": {}, "unknown_q": {}}, registry_path=reg)

        assert "myp" in result
        assert "unknown_q" not in result


# ---------------------------------------------------------------------------
# build() — exact provider names (parametrized per YAML entry)
# ---------------------------------------------------------------------------


def _make_stub_module_for_provider(provider: str) -> MagicMock:
    """Return a MagicMock module whose class attribute is a stub adapter."""
    stub_cls = _stub_adapter_cls(provider)
    mod = MagicMock()
    # We'll be patching importlib.import_module, so the class name doesn't matter
    # as long as the mock returns our stub.
    mod.FakeCls = stub_cls
    return mod


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_exact_provider_is_built(provider: str, tmp_path):
    """Each exact provider name in adapters.yaml should produce an adapter instance."""
    stub_cls = _stub_adapter_cls(provider)
    fake_module = MagicMock()
    fake_module.FakeCls = stub_cls

    yaml_content = (
        f'version: "1.0"\nadapters:\n  {provider}:\n    module: fake_mod\n    class: FakeCls\nprefixes: {{}}\n'
    )
    reg = tmp_path / "adapters.yaml"
    reg.write_text(yaml_content)

    with patch("importlib.import_module", return_value=fake_module):
        result = build({provider: {"enabled": True}}, registry_path=reg)

    assert provider in result
    assert isinstance(result[provider], stub_cls)


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_exact_provider_config_passed_through(provider: str, tmp_path):
    """The cfg dict given to build() is forwarded unchanged to the adapter class."""
    received_cfgs: list[dict] = []

    class RecordCls(BaseAdapter):
        def __init__(self, cfg: dict):
            received_cfgs.append(cfg)
            super().__init__(provider, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_module = MagicMock()
    fake_module.RecordCls = RecordCls

    yaml_content = (
        f'version: "1.0"\nadapters:\n  {provider}:\n    module: fake_mod\n    class: RecordCls\nprefixes: {{}}\n'
    )
    reg = tmp_path / "adapters.yaml"
    reg.write_text(yaml_content)

    cfg_in = {"enabled": True, "sentinel": f"cfg_for_{provider}"}
    with patch("importlib.import_module", return_value=fake_module):
        build({provider: cfg_in}, registry_path=reg)

    assert len(received_cfgs) == 1
    assert received_cfgs[0]["sentinel"] == f"cfg_for_{provider}"


# ---------------------------------------------------------------------------
# build() — prefix matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", PREFIX_PROVIDERS)
def test_prefix_provider_matched_and_built(provider: str, tmp_path):
    """Any provider starting with 'ollama' should match the prefix entry."""
    stub_cls = _stub_adapter_cls_with_name("OllamaStub")
    fake_module = MagicMock()
    fake_module.OllamaStub = stub_cls

    yaml_content = (
        'version: "1.0"\n'
        "adapters: {}\n"
        "prefixes:\n"
        "  ollama:\n"
        "    module: fake_mod\n"
        "    class: OllamaStub\n"
        "    pass_name: true\n"
    )
    reg = tmp_path / "adapters.yaml"
    reg.write_text(yaml_content)

    with patch("importlib.import_module", return_value=fake_module):
        result = build({provider: {"host": "localhost"}}, registry_path=reg)

    assert provider in result
    assert isinstance(result[provider], stub_cls)


def test_prefix_pass_name_forwards_provider_name(tmp_path):
    """When pass_name=true the adapter receives the actual provider key, not the prefix."""
    names_received: list[str] = []

    class NameCapture(BaseAdapter):
        def __init__(self, name: str, cfg: dict):
            names_received.append(name)
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_module = MagicMock()
    fake_module.NameCapture = NameCapture

    yaml_content = (
        'version: "1.0"\n'
        "adapters: {}\n"
        "prefixes:\n"
        "  ollama:\n"
        "    module: fake_mod\n"
        "    class: NameCapture\n"
        "    pass_name: true\n"
    )
    reg = tmp_path / "adapters.yaml"
    reg.write_text(yaml_content)

    with patch("importlib.import_module", return_value=fake_module):
        build({"ollama_my_desktop": {"host": "192.168.1.10"}}, registry_path=reg)

    assert names_received == ["ollama_my_desktop"]


def test_exact_match_takes_priority_over_prefix(tmp_path):
    """If a provider matches both an exact key and a prefix, exact key wins."""
    exact_calls: list[str] = []
    prefix_calls: list[str] = []

    class ExactCls(BaseAdapter):
        def __init__(self, cfg: dict):
            exact_calls.append("exact")
            super().__init__("ollama", cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    class PrefixCls(BaseAdapter):
        def __init__(self, name: str, cfg: dict):
            prefix_calls.append("prefix")
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_module = MagicMock()
    fake_module.ExactCls = ExactCls
    fake_module.PrefixCls = PrefixCls

    yaml_content = (
        'version: "1.0"\n'
        "adapters:\n"
        "  ollama:\n"
        "    module: fake_mod\n"
        "    class: ExactCls\n"
        "prefixes:\n"
        "  ollama:\n"
        "    module: fake_mod\n"
        "    class: PrefixCls\n"
        "    pass_name: true\n"
    )
    reg = tmp_path / "adapters.yaml"
    reg.write_text(yaml_content)

    with patch("importlib.import_module", return_value=fake_module):
        result = build({"ollama": {}}, registry_path=reg)

    assert "ollama" in result
    assert exact_calls == ["exact"]
    assert prefix_calls == []


# ---------------------------------------------------------------------------
# build() — multiple providers in one call
# ---------------------------------------------------------------------------


def test_build_returns_multiple_adapters(tmp_path):
    """build() accepts several providers and instantiates each independently."""
    call_log: list[str] = []

    def make_cls(pname: str):
        class C(BaseAdapter):
            def __init__(self, cfg: dict):
                call_log.append(pname)
                super().__init__(pname, cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        C.__name__ = f"Cls_{pname}"
        return C

    cls_a = make_cls("alpha")
    cls_b = make_cls("beta")
    fake_module = MagicMock()
    fake_module.ClsA = cls_a
    fake_module.ClsB = cls_b

    yaml_content = (
        'version: "1.0"\n'
        "adapters:\n"
        "  alpha:\n"
        "    module: fake_mod\n"
        "    class: ClsA\n"
        "  beta:\n"
        "    module: fake_mod\n"
        "    class: ClsB\n"
        "prefixes: {}\n"
    )
    reg = tmp_path / "adapters.yaml"
    reg.write_text(yaml_content)

    with patch("importlib.import_module", return_value=fake_module):
        result = build({"alpha": {}, "beta": {}, "gamma": {}}, registry_path=reg)

    assert set(result.keys()) == {"alpha", "beta"}
    assert "gamma" not in result
    assert sorted(call_log) == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# build() — custom registry_path
# ---------------------------------------------------------------------------


def test_build_uses_provided_registry_path(tmp_path):
    """Passing registry_path overrides the module-level default path."""
    stub_cls = _stub_adapter_cls("custom_p")
    fake_module = MagicMock()
    fake_module.CustomCls = stub_cls

    yaml_content = 'version: "1.0"\nadapters:\n  custom_p:\n    module: fake_mod\n    class: CustomCls\nprefixes: {}\n'
    reg = tmp_path / "custom_adapters.yaml"
    reg.write_text(yaml_content)

    with patch("importlib.import_module", return_value=fake_module):
        result = build({"custom_p": {}}, registry_path=reg)

    assert "custom_p" in result


def test_build_uses_default_registry_path_when_none_given():
    """When registry_path=None, the real adapters.yaml is used (smoke test)."""
    # Just confirm no exception with the live registry and zero providers
    result = build({})
    assert isinstance(result, dict)
    assert result == {}


# ---------------------------------------------------------------------------
# build() — real YAML registry smoke test (each exact provider, no network)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_real_registry_has_entry_for_provider(provider: str):
    """Each documented provider name has an entry in the real adapters.yaml."""
    data = _load_registry(_REGISTRY_PATH)
    assert provider in data["adapters"], (
        f"Expected '{provider}' in real adapters.yaml but it was not found. Update EXACT_PROVIDERS in this test file."
    )


def test_real_registry_has_ollama_prefix():
    data = _load_registry(_REGISTRY_PATH)
    assert "ollama" in data["prefixes"]


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_real_registry_entry_has_module_and_class(provider: str):
    data = _load_registry(_REGISTRY_PATH)
    entry = data["adapters"][provider]
    assert "module" in entry, f"'{provider}' registry entry missing 'module' key"
    assert "class" in entry, f"'{provider}' registry entry missing 'class' key"
