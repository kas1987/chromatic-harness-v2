"""Unit tests for AdapterFactory + AdapterError (bead chromatic-harness-v2-u8uj.3)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from router.adapters.base import AdapterError


# ── AdapterError ─────────────────────────────────────────────────────────────


def test_adapter_error_is_exception():
    err = AdapterError("sdk missing", provider="anthropic")
    assert isinstance(err, Exception)
    assert str(err) == "sdk missing"
    assert err.provider == "anthropic"
    assert err.cause is None


def test_adapter_error_wraps_cause():
    cause = ImportError("no module")
    err = AdapterError("sdk missing", provider="openai", cause=cause)
    assert err.cause is cause


def test_adapter_error_default_provider_empty():
    err = AdapterError("oops")
    assert err.provider == ""


# ── AdapterFactory.build() ───────────────────────────────────────────────────


def _write_registry(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "adapters.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_build_exact_match(tmp_path):
    registry = _write_registry(
        tmp_path,
        """\
        version: "1.0"
        adapters:
          mock:
            module: "router.adapters.mock"
            class: "MockAdapter"
        prefixes: {}
        """,
    )
    from router.adapters.adapter_factory import build
    from router.adapters.mock import MockAdapter

    result = build({"mock": {}}, registry_path=registry)
    assert "mock" in result
    assert isinstance(result["mock"], MockAdapter)


def test_build_prefix_match(tmp_path):
    registry = _write_registry(
        tmp_path,
        """\
        version: "1.0"
        adapters: {}
        prefixes:
          ollama:
            module: "router.adapters.ollama_remote"
            class: "OllamaRemoteAdapter"
            pass_name: true
        """,
    )
    from router.adapters.adapter_factory import build
    from router.adapters.ollama_remote import OllamaRemoteAdapter

    result = build({"ollama_local": {"enabled": False}}, registry_path=registry)
    assert "ollama_local" in result
    assert isinstance(result["ollama_local"], OllamaRemoteAdapter)


def test_build_unknown_provider_skipped(tmp_path):
    registry = _write_registry(
        tmp_path,
        """\
        version: "1.0"
        adapters: {}
        prefixes: {}
        """,
    )
    from router.adapters.adapter_factory import build

    result = build({"nonexistent_xyz": {}}, registry_path=registry)
    assert result == {}


def test_build_pass_name_passes_provider_name(tmp_path):
    registry = _write_registry(
        tmp_path,
        """\
        version: "1.0"
        adapters: {}
        prefixes:
          ollama:
            module: "router.adapters.ollama_remote"
            class: "OllamaRemoteAdapter"
            pass_name: true
        """,
    )
    from router.adapters.adapter_factory import build

    result = build({"ollama_remote_desktop": {"enabled": False}}, registry_path=registry)
    assert result["ollama_remote_desktop"].name == "ollama_remote_desktop"


# ── Adapter raises AdapterError (not RuntimeError) ───────────────────────────


def test_anthropic_adapter_raises_adapter_error_on_missing_sdk(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def block_anthropic(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("no module named anthropic")
        return real_import(name, *args, **kwargs)

    from router.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter({})
    adapter._client = None
    monkeypatch.setattr(builtins, "__import__", block_anthropic)

    with pytest.raises(AdapterError) as exc_info:
        adapter._get_client()
    assert exc_info.value.provider == "anthropic"


def test_openai_adapter_raises_adapter_error_on_missing_sdk(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def block_openai(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no module named openai")
        return real_import(name, *args, **kwargs)

    from router.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter({})
    adapter._client = None
    monkeypatch.setattr(builtins, "__import__", block_openai)

    with pytest.raises(AdapterError) as exc_info:
        adapter._get_client()
    assert exc_info.value.provider == "openai"
