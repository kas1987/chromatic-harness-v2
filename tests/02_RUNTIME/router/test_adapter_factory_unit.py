"""Unit tests for router.adapters.adapter_factory.build().

# DEFICIENCIES NOTED
#
# 1. SILENT SKIP ON UNKNOWN PROVIDERS: The factory silently skips unknown
#    providers (by design), which means typos in providers.yaml or provider
#    configs produce no error and no adapter. Callers must diff the returned
#    dict against the input themselves to detect missing adapters.
#
# 2. NO ERROR HANDLING IN _instantiate(): If a registry entry points to a
#    bad module path or wrong class name, ImportError / AttributeError
#    propagates uncaught from build(). A single broken adapter kills the
#    entire build call, even for unrelated providers in the same dict.
#
# 3. NO SKIP DIAGNOSTICS: There is no public API to introspect which providers
#    were silently skipped; callers receive a plain dict with no diff against
#    what was requested.
#
# 4. REGISTRY RELOADED ON EVERY CALL: _load_registry() reads and parses the
#    YAML file on every build() invocation with no caching. A malformed YAML
#    blocks all adapters even if only one provider was requested.
#
# 5. PREFIX PRIORITY IS IMPLICIT: Prefix matching iterates in dict-insertion
#    order (CPython 3.7+). There is no explicit priority mechanism; if two
#    prefix entries both match a provider name, the first one silently wins.
#
# 6. cfg IS NOT VALIDATED: Any value including None is accepted as cfg and
#    forwarded directly to the adapter constructor. Passing None can cause
#    AttributeError inside the adapter __init__ if it calls .get() on cfg.
#
# 7. NO MOCK PROVIDER IN REGISTRY: The real adapters.yaml has no "mock" entry,
#    so test harnesses that want a lightweight adapter must supply a custom
#    registry_path. This makes integration-style tests with the real registry
#    depend on actual SDK presence.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure 02_RUNTIME is on sys.path before importing router packages.
# pytest.ini lists "pythonpath = 02_RUNTIME" but the installed pytest version
# does not support that option, so we insert manually here.
_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import router.adapters.adapter_factory as factory_mod  # noqa: F401
from router.adapters.adapter_factory import _instantiate, _load_registry, build
from router.adapters.base import BaseAdapter

# ---------------------------------------------------------------------------
# Real registry location (used for smoke tests against the live adapters.yaml)
# ---------------------------------------------------------------------------

_REGISTRY_PATH = Path(__file__).resolve().parents[4] / "02_RUNTIME" / "router" / "adapters" / "adapters.yaml"

# Exact adapter names that must exist in the real adapters.yaml.
# Keep in sync with adapters.yaml when providers are added or removed.
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

# Provider names that should all match the "ollama" prefix rule.
PREFIX_PROVIDERS = [
    "ollama",
    "ollama_local",
    "ollama_remote_desktop",
    "ollama_gpu_rig",
    "ollama_anything_else",
]


# ---------------------------------------------------------------------------
# Stub adapter helpers
# ---------------------------------------------------------------------------


def _make_cfg_only_cls(label: str = "stub") -> type:
    """Return a concrete BaseAdapter whose constructor takes only (cfg)."""

    class _CfgOnly(BaseAdapter):
        def __init__(self, cfg: dict):
            super().__init__(label, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    _CfgOnly.__name__ = f"CfgOnly_{label}"
    return _CfgOnly


def _make_name_cfg_cls(label: str = "stub_named") -> type:
    """Return a concrete BaseAdapter whose constructor takes (name, cfg)."""

    class _NameCfg(BaseAdapter):
        def __init__(self, name: str, cfg: dict):
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    _NameCfg.__name__ = f"NameCfg_{label}"
    return _NameCfg


def _write_registry(tmp_path: Path, content: str) -> Path:
    """Write YAML content to tmp_path/adapters.yaml and return the path."""
    reg = tmp_path / "adapters.yaml"
    reg.write_text(content, encoding="utf-8")
    return reg


def _exact_yaml(provider: str, cls_name: str = "FakeCls", pass_name: bool = False) -> str:
    pn_line = "    pass_name: true\n" if pass_name else ""
    return (
        f'version: "1.0"\n'
        f"adapters:\n"
        f"  {provider}:\n"
        f"    module: fake_mod\n"
        f"    class: {cls_name}\n"
        f"{pn_line}"
        f"prefixes: {{}}\n"
    )


def _prefix_yaml(prefix: str, cls_name: str = "FakeCls", pass_name: bool = True) -> str:
    pn_line = "    pass_name: true\n" if pass_name else ""
    return (
        f'version: "1.0"\n'
        f"adapters: {{}}\n"
        f"prefixes:\n"
        f"  {prefix}:\n"
        f"    module: fake_mod\n"
        f"    class: {cls_name}\n"
        f"{pn_line}"
    )


# ---------------------------------------------------------------------------
# _load_registry
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    def test_loads_real_yaml_returns_dict(self):
        data = _load_registry(_REGISTRY_PATH)
        assert isinstance(data, dict)

    def test_real_yaml_has_adapters_key(self):
        data = _load_registry(_REGISTRY_PATH)
        assert "adapters" in data

    def test_real_yaml_has_prefixes_key(self):
        data = _load_registry(_REGISTRY_PATH)
        assert "prefixes" in data

    def test_adapters_value_is_dict(self):
        data = _load_registry(_REGISTRY_PATH)
        assert isinstance(data["adapters"], dict)

    def test_prefixes_value_is_dict(self):
        data = _load_registry(_REGISTRY_PATH)
        assert isinstance(data["prefixes"], dict)

    def test_raises_import_error_when_pyyaml_missing(self):
        with patch.dict("sys.modules", {"yaml": None}):
            with pytest.raises(ImportError, match="pyyaml"):
                _load_registry(_REGISTRY_PATH)

    def test_error_message_contains_install_hint(self):
        with patch.dict("sys.modules", {"yaml": None}):
            with pytest.raises(ImportError, match="pip install pyyaml"):
                _load_registry(_REGISTRY_PATH)

    def test_raises_on_nonexistent_file(self, tmp_path):
        with pytest.raises(Exception):
            _load_registry(tmp_path / "does_not_exist.yaml")

    def test_loads_minimal_valid_yaml(self, tmp_path):
        reg = _write_registry(tmp_path, 'version: "1.0"\nadapters: {}\nprefixes: {}\n')
        data = _load_registry(reg)
        assert data["adapters"] == {}
        assert data["prefixes"] == {}

    def test_openai_entry_references_openai_module(self):
        data = _load_registry(_REGISTRY_PATH)
        entry = data["adapters"].get("openai", {})
        assert "module" in entry
        assert "openai" in entry["module"].lower()


# ---------------------------------------------------------------------------
# _instantiate
# ---------------------------------------------------------------------------


class TestInstantiate:
    def test_calls_cls_with_cfg_when_pass_name_absent(self):
        StubCls = _make_cfg_only_cls("p1")
        fake_mod = MagicMock()
        fake_mod.FakeCls = StubCls
        entry = {"module": "fake_mod", "class": "FakeCls"}

        with patch("importlib.import_module", return_value=fake_mod):
            inst = _instantiate(entry, "p1", {"k": "v"})

        assert isinstance(inst, StubCls)

    def test_calls_cls_with_cfg_when_pass_name_false(self):
        received: list[dict] = []

        class _Spy(BaseAdapter):
            def __init__(self, cfg: dict):
                received.append(cfg)
                super().__init__("spy", cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        fake_mod = MagicMock()
        fake_mod._Spy = _Spy
        entry = {"module": "fake_mod", "class": "_Spy", "pass_name": False}
        cfg = {"model": "gpt-4o", "enabled": True}

        with patch("importlib.import_module", return_value=fake_mod):
            _instantiate(entry, "openai", cfg)

        assert received == [cfg]

    def test_calls_cls_with_name_and_cfg_when_pass_name_true(self):
        captured: list[tuple] = []

        class _SpyNamed(BaseAdapter):
            def __init__(self, name: str, cfg: dict):
                captured.append((name, cfg))
                super().__init__(name, cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        fake_mod = MagicMock()
        fake_mod._SpyNamed = _SpyNamed
        entry = {"module": "fake_mod", "class": "_SpyNamed", "pass_name": True}
        cfg = {"host": "192.168.1.5"}

        with patch("importlib.import_module", return_value=fake_mod):
            _instantiate(entry, "ollama_desktop", cfg)

        assert len(captured) == 1
        assert captured[0] == ("ollama_desktop", cfg)

    def test_name_forwarded_verbatim_when_pass_name_true(self):
        names: list[str] = []

        class _NameOnly(BaseAdapter):
            def __init__(self, name: str, cfg: dict):
                names.append(name)
                super().__init__(name, cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        fake_mod = MagicMock()
        fake_mod._NameOnly = _NameOnly
        entry = {"module": "fake_mod", "class": "_NameOnly", "pass_name": True}

        with patch("importlib.import_module", return_value=fake_mod):
            _instantiate(entry, "ollama_special_rig_xyz", {})

        assert names == ["ollama_special_rig_xyz"]

    def test_propagates_module_not_found_error(self):
        entry = {"module": "no_such_module_zzz", "class": "Foo"}
        with pytest.raises(ModuleNotFoundError):
            _instantiate(entry, "bad", {})

    def test_propagates_attribute_error_for_missing_class(self):
        dummy = types.ModuleType("_dummy_mod_test")
        with patch.dict("sys.modules", {"_dummy_mod_test": dummy}):
            entry = {"module": "_dummy_mod_test", "class": "NonExistentClass"}
            with pytest.raises(AttributeError):
                _instantiate(entry, "provider", {})

    def test_imports_module_by_name_in_entry(self):
        StubCls = _make_cfg_only_cls("import_check")
        fake_mod = MagicMock()
        fake_mod.FakeCls = StubCls
        entry = {"module": "my.special.module", "class": "FakeCls"}

        with patch("importlib.import_module", return_value=fake_mod) as mock_import:
            _instantiate(entry, "p", {})

        mock_import.assert_called_once_with("my.special.module")


# ---------------------------------------------------------------------------
# build() — empty and unknown provider behaviour
# ---------------------------------------------------------------------------


class TestBuildEmpty:
    def test_empty_providers_returns_empty_dict(self):
        result = build({}, registry_path=_REGISTRY_PATH)
        assert result == {}

    def test_single_unknown_provider_silently_skipped(self):
        result = build({"__no_such_provider__": {}}, registry_path=_REGISTRY_PATH)
        assert result == {}

    def test_multiple_unknown_providers_all_skipped(self):
        result = build({"x1": {}, "x2": {}, "x3": {}}, registry_path=_REGISTRY_PATH)
        assert result == {}

    def test_unknown_provider_does_not_raise(self):
        # Must never raise; always silently skip
        build({"totally_made_up_provider": None}, registry_path=_REGISTRY_PATH)

    def test_mixed_known_unknown_only_known_returned(self, tmp_path):
        StubCls = _make_cfg_only_cls("myp")
        fake_mod = MagicMock()
        fake_mod.FakeCls = StubCls
        reg = _write_registry(tmp_path, _exact_yaml("myp"))

        with patch("importlib.import_module", return_value=fake_mod):
            result = build({"myp": {}, "unknown_q": {}}, registry_path=reg)

        assert "myp" in result
        assert "unknown_q" not in result
        assert len(result) == 1


# ---------------------------------------------------------------------------
# build() — exact provider names, one parametrized test per registry entry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_exact_provider_produces_adapter_instance(provider: str, tmp_path):
    """Each exact provider name from the registry must produce a BaseAdapter instance."""
    StubCls = _make_cfg_only_cls(provider)
    fake_mod = MagicMock()
    fake_mod.FakeCls = StubCls
    reg = _write_registry(tmp_path, _exact_yaml(provider))

    with patch("importlib.import_module", return_value=fake_mod):
        result = build({provider: {"enabled": True}}, registry_path=reg)

    assert provider in result
    assert isinstance(result[provider], StubCls)


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_exact_provider_key_preserved_in_result(provider: str, tmp_path):
    """The key in the returned dict must equal the provider name, not the class name."""
    StubCls = _make_cfg_only_cls(provider)
    fake_mod = MagicMock()
    fake_mod.FakeCls = StubCls
    reg = _write_registry(tmp_path, _exact_yaml(provider))

    with patch("importlib.import_module", return_value=fake_mod):
        result = build({provider: {}}, registry_path=reg)

    assert list(result.keys()) == [provider]


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_exact_provider_cfg_forwarded_unchanged(provider: str, tmp_path):
    """The cfg dict given to build() must arrive unmodified at the adapter constructor."""
    received: list[dict] = []

    class _Record(BaseAdapter):
        def __init__(self, cfg: dict):
            received.append(dict(cfg))
            super().__init__(provider, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_mod = MagicMock()
    fake_mod.RecordCls = _Record
    reg = _write_registry(tmp_path, _exact_yaml(provider, "RecordCls"))

    sentinel_cfg = {"enabled": True, "sentinel": f"for_{provider}", "extra": 42}
    with patch("importlib.import_module", return_value=fake_mod):
        build({provider: sentinel_cfg}, registry_path=reg)

    assert len(received) == 1
    assert received[0]["sentinel"] == f"for_{provider}"
    assert received[0]["extra"] == 42


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_real_registry_has_exact_provider_entry(provider: str):
    """Every provider in EXACT_PROVIDERS must exist in the real adapters.yaml."""
    data = _load_registry(_REGISTRY_PATH)
    assert provider in data["adapters"], (
        f"'{provider}' is missing from the real adapters.yaml. Update EXACT_PROVIDERS in this test file."
    )


@pytest.mark.parametrize("provider", EXACT_PROVIDERS)
def test_real_registry_entry_has_required_keys(provider: str):
    """Every registry entry must have both 'module' and 'class' keys."""
    data = _load_registry(_REGISTRY_PATH)
    entry = data["adapters"][provider]
    assert "module" in entry, f"'{provider}' entry missing 'module'"
    assert "class" in entry, f"'{provider}' entry missing 'class'"


# ---------------------------------------------------------------------------
# build() — prefix matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", PREFIX_PROVIDERS)
def test_prefix_provider_matched_and_adapter_created(provider: str, tmp_path):
    """Any provider name starting with 'ollama' should match the prefix rule."""
    StubCls = _make_name_cfg_cls("OllamaStub")
    fake_mod = MagicMock()
    fake_mod.OllamaStub = StubCls
    reg = _write_registry(tmp_path, _prefix_yaml("ollama", "OllamaStub"))

    with patch("importlib.import_module", return_value=fake_mod):
        result = build({provider: {"host": "localhost"}}, registry_path=reg)

    assert provider in result
    assert isinstance(result[provider], StubCls)


@pytest.mark.parametrize("provider", PREFIX_PROVIDERS)
def test_prefix_provider_name_forwarded_to_constructor(provider: str, tmp_path):
    """The exact provider key — not the prefix string — must be passed as name."""
    names: list[str] = []

    class _Capture(BaseAdapter):
        def __init__(self, name: str, cfg: dict):
            names.append(name)
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_mod = MagicMock()
    fake_mod._Capture = _Capture
    reg = _write_registry(tmp_path, _prefix_yaml("ollama", "_Capture"))

    with patch("importlib.import_module", return_value=fake_mod):
        build({provider: {}}, registry_path=reg)

    assert names == [provider]


def test_exact_match_takes_priority_over_prefix(tmp_path):
    """When a provider matches both an exact entry and a prefix, the exact entry wins."""
    exact_calls: list[str] = []
    prefix_calls: list[str] = []

    class _ExactCls(BaseAdapter):
        def __init__(self, cfg: dict):
            exact_calls.append("exact")
            super().__init__("ollama", cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    class _PrefixCls(BaseAdapter):
        def __init__(self, name: str, cfg: dict):
            prefix_calls.append("prefix")
            super().__init__(name, cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_mod = MagicMock()
    fake_mod._ExactCls = _ExactCls
    fake_mod._PrefixCls = _PrefixCls

    yaml_content = (
        'version: "1.0"\n'
        "adapters:\n"
        "  ollama:\n"
        "    module: fake_mod\n"
        "    class: _ExactCls\n"
        "prefixes:\n"
        "  ollama:\n"
        "    module: fake_mod\n"
        "    class: _PrefixCls\n"
        "    pass_name: true\n"
    )
    reg = _write_registry(tmp_path, yaml_content)

    with patch("importlib.import_module", return_value=fake_mod):
        result = build({"ollama": {}}, registry_path=reg)

    assert "ollama" in result
    assert exact_calls == ["exact"]
    assert prefix_calls == []


def test_provider_not_matching_any_prefix_is_skipped(tmp_path):
    """A name that doesn't start with any registered prefix must be silently skipped."""
    reg = _write_registry(tmp_path, _prefix_yaml("ollama", "FakeCls"))
    result = build({"lmstudio_local": {}}, registry_path=reg)
    assert result == {}


def test_prefix_without_pass_name_uses_cfg_only(tmp_path):
    """A prefix entry with pass_name absent/false must call the constructor with (cfg) only."""
    received: list = []

    class _CfgOnlyPrefix(BaseAdapter):
        def __init__(self, cfg: dict):
            received.append(cfg)
            super().__init__("prefix_p", cfg or {})

        async def health(self):  # pragma: no cover
            ...

        async def complete(self, req):  # pragma: no cover
            ...

    fake_mod = MagicMock()
    fake_mod._CfgOnlyPrefix = _CfgOnlyPrefix
    reg = _write_registry(tmp_path, _prefix_yaml("myprefix", "_CfgOnlyPrefix", pass_name=False))

    cfg_in = {"host": "test-host"}
    with patch("importlib.import_module", return_value=fake_mod):
        build({"myprefix_something": cfg_in}, registry_path=reg)

    assert received == [cfg_in]


def test_real_registry_has_ollama_prefix():
    data = _load_registry(_REGISTRY_PATH)
    assert "ollama" in data["prefixes"]


def test_real_registry_ollama_prefix_has_pass_name_true():
    data = _load_registry(_REGISTRY_PATH)
    entry = data["prefixes"]["ollama"]
    assert entry.get("pass_name") is True


# ---------------------------------------------------------------------------
# build() — multiple providers in one call
# ---------------------------------------------------------------------------


def test_build_multiple_providers_returned(tmp_path):
    """build() with N known providers must return exactly N adapters."""
    call_log: list[str] = []

    def _make_cls(pname: str):
        class _C(BaseAdapter):
            def __init__(self, cfg: dict):
                call_log.append(pname)
                super().__init__(pname, cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        _C.__name__ = f"Cls_{pname}"
        return _C

    cls_a = _make_cls("alpha")
    cls_b = _make_cls("beta")
    fake_mod = MagicMock()
    fake_mod.ClsA = cls_a
    fake_mod.ClsB = cls_b

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
    reg = _write_registry(tmp_path, yaml_content)

    with patch("importlib.import_module", return_value=fake_mod):
        result = build({"alpha": {}, "beta": {}, "gamma_unknown": {}}, registry_path=reg)

    assert set(result.keys()) == {"alpha", "beta"}
    assert "gamma_unknown" not in result
    assert sorted(call_log) == ["alpha", "beta"]


def test_build_each_provider_cfg_is_independent(tmp_path):
    """Each provider must receive its own cfg dict; they must not share identity."""
    cfgs_received: dict[str, dict] = {}

    def _make_cls(pname: str):
        class _C(BaseAdapter):
            def __init__(self, cfg: dict):
                cfgs_received[pname] = cfg
                super().__init__(pname, cfg or {})

            async def health(self):  # pragma: no cover
                ...

            async def complete(self, req):  # pragma: no cover
                ...

        _C.__name__ = f"Cls_{pname}"
        return _C

    fake_mod = MagicMock()
    fake_mod.ClsX = _make_cls("x")
    fake_mod.ClsY = _make_cls("y")

    yaml_content = (
        'version: "1.0"\n'
        "adapters:\n"
        "  x:\n"
        "    module: fake_mod\n"
        "    class: ClsX\n"
        "  y:\n"
        "    module: fake_mod\n"
        "    class: ClsY\n"
        "prefixes: {}\n"
    )
    reg = _write_registry(tmp_path, yaml_content)
    cfg_x = {"val": 1}
    cfg_y = {"val": 2}

    with patch("importlib.import_module", return_value=fake_mod):
        build({"x": cfg_x, "y": cfg_y}, registry_path=reg)

    assert cfgs_received["x"] is cfg_x
    assert cfgs_received["y"] is cfg_y
    assert cfgs_received["x"] is not cfgs_received["y"]


# ---------------------------------------------------------------------------
# build() — custom registry_path parameter
# ---------------------------------------------------------------------------


def test_build_uses_provided_registry_path(tmp_path):
    """Passing registry_path= must override the module-level default path."""
    StubCls = _make_cfg_only_cls("custom_p")
    fake_mod = MagicMock()
    fake_mod.CustomCls = StubCls
    reg = _write_registry(tmp_path, _exact_yaml("custom_p", "CustomCls"))

    with patch("importlib.import_module", return_value=fake_mod):
        result = build({"custom_p": {}}, registry_path=reg)

    assert "custom_p" in result


def test_build_default_registry_path_when_none_given():
    """When registry_path=None the real adapters.yaml is loaded; zero providers is safe."""
    result = build({})
    assert isinstance(result, dict)
    assert result == {}


def test_provider_only_in_custom_registry_absent_from_default(tmp_path):
    """A provider present only in a custom registry must NOT appear with the default registry."""
    StubCls = _make_cfg_only_cls("only_in_custom")
    fake_mod = MagicMock()
    fake_mod.FakeCls = StubCls
    reg = _write_registry(tmp_path, _exact_yaml("only_in_custom"))

    # Custom registry: provider found
    with patch("importlib.import_module", return_value=fake_mod):
        result_custom = build({"only_in_custom": {}}, registry_path=reg)
    assert "only_in_custom" in result_custom

    # Default registry: provider silently skipped
    result_default = build({"only_in_custom": {}})
    assert "only_in_custom" not in result_default


# ---------------------------------------------------------------------------
# build() — error propagation from _instantiate
# ---------------------------------------------------------------------------


def test_build_propagates_import_error_for_bad_module(tmp_path):
    """If the registry references a non-existent module, ImportError must propagate."""
    reg = _write_registry(
        tmp_path,
        ('version: "1.0"\nadapters:\n  p:\n    module: no_such_mod_zzz\n    class: Cls\nprefixes: {}\n'),
    )
    with pytest.raises((ImportError, ModuleNotFoundError)):
        build({"p": {}}, registry_path=reg)


def test_build_propagates_attribute_error_for_missing_class(tmp_path):
    """If the registry class name doesn't exist in the module, AttributeError propagates."""
    dummy_mod = types.ModuleType("_test_dummy_mod")
    reg = _write_registry(
        tmp_path,
        ('version: "1.0"\nadapters:\n  p:\n    module: _test_dummy_mod\n    class: Ghost\nprefixes: {}\n'),
    )
    with patch.dict("sys.modules", {"_test_dummy_mod": dummy_mod}):
        with pytest.raises(AttributeError):
            build({"p": {}}, registry_path=reg)
