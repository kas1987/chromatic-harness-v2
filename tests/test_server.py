"""Tests for 02_RUNTIME/chromatic_mcp/server.py — non-network functions only.

Network/stdio calls (run_stdio, main) are tested only for their error-path
behaviour when mcp is absent; _build_server and handler dispatch are tested
against the handlers module directly to avoid real subprocess/socket I/O.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SERVER_PATH = _REPO / "02_RUNTIME" / "chromatic_mcp" / "server.py"
_HANDLERS_PATH = _REPO / "02_RUNTIME" / "chromatic_mcp" / "handlers.py"


def _load_handlers(name: str = "_srv_handlers"):
    spec = importlib.util.spec_from_file_location(name, _HANDLERS_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_server(name: str = "_srv_mod"):
    """Load server.py; mcp is optional so absence is handled gracefully."""
    spec = importlib.util.spec_from_file_location(name, _SERVER_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def handlers():
    name = "_srv_handlers"
    sys.modules.pop(name, None)
    mod = _load_handlers(name)
    yield mod
    sys.modules.pop(name, None)


@pytest.fixture()
def smod():
    name = "_srv_mod"
    sys.modules.pop(name, None)
    # Ensure chromatic_mcp.handlers is importable (needed by server module)
    sys.path.insert(0, str(_REPO / "02_RUNTIME"))
    mod = _load_server(name)
    yield mod
    sys.modules.pop(name, None)


class TestServer:

    # 1. import clean --------------------------------------------------------
    def test_import_clean(self):
        """server.py loads without error; SERVER_NAME is set."""
        name = "_srv_import_clean"
        sys.modules.pop(name, None)
        sys.path.insert(0, str(_REPO / "02_RUNTIME"))
        try:
            mod = _load_server(name)
            assert mod.SERVER_NAME == "chromatic-harness"
            assert hasattr(mod, "run_stdio")
            assert hasattr(mod, "main")
        finally:
            sys.modules.pop(name, None)

    # 2. happy path — handlers.list_tool_specs returns well-formed list ------
    def test_list_tool_specs_returns_list(self, handlers):
        """list_tool_specs returns a non-empty list of tool dicts."""
        specs = handlers.list_tool_specs()
        assert isinstance(specs, list)
        assert len(specs) >= 5
        for spec in specs:
            assert "name" in spec
            assert "description" in spec
            assert "inputSchema" in spec

    def test_list_tool_specs_names_are_strings(self, handlers):
        """Every tool spec has a non-empty string name."""
        for spec in handlers.list_tool_specs():
            assert isinstance(spec["name"], str) and spec["name"]

    # 3. error path — call_tool unknown name ---------------------------------
    def test_call_tool_unknown_name(self, handlers):
        """call_tool returns {ok: False} for an unregistered tool name."""
        result = handlers.call_tool("no_such_tool_xyz", {})
        assert result["ok"] is False
        assert "unknown tool" in result.get("error", "")

    def test_call_tool_unknown_name_no_exception(self, handlers):
        """call_tool never raises; always returns a dict."""
        result = handlers.call_tool("__nonexistent__")
        assert isinstance(result, dict)
        assert "ok" in result

    # 4. boundary — call_tool with None arguments ----------------------------
    def test_call_tool_with_none_arguments(self, handlers, monkeypatch):
        """call_tool accepts None arguments and coerces to empty dict."""
        # Patch the underlying handler so no subprocess is spawned
        monkeypatch.setitem(handlers.HANDLERS, "beads_ready", lambda _: {"ok": True, "stdout": ""})
        result = handlers.call_tool("beads_ready", None)
        assert result["ok"] is True

    def test_call_tool_with_empty_arguments(self, handlers, monkeypatch):
        """call_tool accepts empty dict arguments."""
        monkeypatch.setitem(handlers.HANDLERS, "beads_ready", lambda _: {"ok": True, "stdout": ""})
        result = handlers.call_tool("beads_ready", {})
        assert result["ok"] is True

    # 5. fail-open — run_stdio raises when mcp is absent ---------------------
    def test_run_stdio_raises_without_mcp(self, smod):
        """run_stdio raises RuntimeError when mcp package is not installed."""
        if smod.Server is not None:
            pytest.skip("mcp package is installed; skip absence test")
        import asyncio
        with pytest.raises(RuntimeError, match="mcp package required"):
            asyncio.run(smod.run_stdio())

    # 6. smoke — _session_id helper ------------------------------------------
    def test_session_id_fallback_anonymous(self, handlers, tmp_path):
        """_session_id returns 'anonymous-session' when no session file exists."""
        # Temporarily redirect REPO_ROOT so the file lookup doesn't find anything
        original = handlers.REPO_ROOT
        handlers.REPO_ROOT = tmp_path
        try:
            sid = handlers._session_id(None)
            assert sid == "anonymous-session"
        finally:
            handlers.REPO_ROOT = original

    def test_session_id_uses_provided_value(self, handlers):
        """_session_id returns the provided value when non-empty."""
        assert handlers._session_id("my-session-42") == "my-session-42"

    def test_session_id_strips_whitespace(self, handlers):
        """_session_id strips leading/trailing whitespace from provided value."""
        assert handlers._session_id("  abc  ") == "abc"

    # 7. smoke — all expected tool names are registered ----------------------
    def test_all_handler_names_match_spec_names(self, handlers):
        """HANDLERS dict keys match all names returned by list_tool_specs."""
        spec_names = {s["name"] for s in handlers.list_tool_specs()}
        handler_names = set(handlers.HANDLERS.keys())
        assert spec_names == handler_names

    # 8. smoke — call_tool wraps handler exceptions in ok=False --------------
    def test_call_tool_wraps_handler_exception(self, handlers, monkeypatch):
        """If a handler raises, call_tool returns ok=False with error text."""
        def _boom(_):
            raise RuntimeError("simulated failure")

        monkeypatch.setitem(handlers.HANDLERS, "beads_ready", _boom)
        result = handlers.call_tool("beads_ready", {})
        assert result["ok"] is False
        assert "simulated failure" in result.get("error", "")

    # 9. _run_script returns structured dict ---------------------------------
    def test_run_script_returns_structured_dict(self, handlers, monkeypatch):
        """_run_script always returns a dict with ok, exit_code, stdout, stderr."""
        import subprocess

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "hello"
        fake_result.stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        result = handlers._run_script("fake_script.py")
        assert result["ok"] is True
        assert result["exit_code"] == 0
        assert "stdout" in result
        assert "stderr" in result

    def test_run_script_non_zero_exit_is_not_ok(self, handlers, monkeypatch):
        """_run_script returns ok=False for non-zero exit codes."""
        import subprocess

        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = ""
        fake_result.stderr = "error output"

        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        result = handlers._run_script("fake_script.py")
        assert result["ok"] is False

    # 10. SERVER_NAME constant -----------------------------------------------
    def test_server_name_constant(self, smod):
        """SERVER_NAME must be the canonical harness identifier."""
        assert smod.SERVER_NAME == "chromatic-harness"

    # 11. intake_queue_list integration (mocked list_queued) -----------------
    def test_intake_queue_list_returns_items(self, handlers, monkeypatch):
        """intake_queue_list wraps list_queued and returns count + items."""
        import intake.queue as iq

        fake_entry = MagicMock()
        fake_entry.to_dict.return_value = {"id": "x", "status": "queued", "title": "t"}
        monkeypatch.setattr(iq, "list_queued", lambda **kw: [fake_entry])
        result = handlers.intake_queue_list()
        assert result["ok"] is True
        assert result["count"] == 1
        assert len(result["items"]) == 1
