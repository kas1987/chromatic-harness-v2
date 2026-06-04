"""Unit tests for 02_RUNTIME/chromatic_mcp/server.py.

Tests cover:
- SERVER_NAME constant
- run_stdio() raises RuntimeError when MCP package is unavailable
- _build_server() creates a Server and registers list_tools / call_tool handlers
- handle_list_tools() builds types.Tool objects from list_tool_specs()
- handle_call_tool() serializes call_tool output to JSON and wraps it in TextContent
- handle_call_tool() with None arguments
- run_stdio() lifecycle: opens stdio_server context, calls server.run()
- main() delegates to asyncio.run(run_stdio())
- _IMPORT_ERROR is None when MCP stubs are registered

# DEFICIENCIES NOTED
# 1. The real `mcp` SDK uses a decorator-based handler registration pattern
#    (@server.list_tools(), @server.call_tool()). In this environment we must
#    stub the Server class such that the decorators capture the handler
#    callables; a plain MagicMock does this automatically (the decorator call
#    returns another callable which is then called on the handler function),
#    but introspecting which handler was registered requires custom stub logic.
#    The tests here extract registered handlers via the stub's call_args tracking.
# 2. stdio_server is an async context manager; testing the full lifecycle
#    requires an async test that awaits the context entry and server.run().
#    This is done with AsyncMock for both read_stream and write_stream.
# 3. server.create_initialization_options() is a method on the Server stub;
#    its return value is passed directly to server.run() and is not validated
#    further by the tests (the real MCP SDK owns that contract).
# 4. The module-level try/except for `from mcp.server import Server` means
#    that once sys.modules["mcp"] is set up before import, Server is NOT None.
#    Tests that want to exercise the Server-is-None path must either import
#    a fresh copy of the module or monkeypatch srv.Server directly after import.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure 02_RUNTIME is on sys.path (mirrors conftest.py setup).
# ---------------------------------------------------------------------------
_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# ---------------------------------------------------------------------------
# Register MCP SDK stubs BEFORE importing server.py so the module-level
# try/except succeeds and Server / stdio_server / types are not None.
# ---------------------------------------------------------------------------


class _FakeTextContent:
    """Minimal stand-in for mcp.types.TextContent."""

    def __init__(self, *, type: str, text: str) -> None:
        self.type = type
        self.text = text

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _FakeTextContent) and self.type == other.type and self.text == other.text

    def __repr__(self) -> str:  # pragma: no cover
        return f"_FakeTextContent(type={self.type!r}, text={self.text!r})"


class _FakeTool:
    """Minimal stand-in for mcp.types.Tool."""

    def __init__(self, *, name: str, description: str, inputSchema: dict) -> None:
        self.name = name
        self.description = description
        self.inputSchema = inputSchema


class _FakeServer:
    """Stub for mcp.server.Server.

    Captures handlers registered via @server.list_tools() and
    @server.call_tool() decorator patterns so they can be retrieved
    and called in tests.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._list_tools_handler = None
        self._call_tool_handler = None
        self.run = AsyncMock(return_value=None)

    def list_tools(self):
        """Decorator factory: register the list-tools handler."""

        def decorator(fn):
            self._list_tools_handler = fn
            return fn

        return decorator

    def call_tool(self):
        """Decorator factory: register the call-tool handler."""

        def decorator(fn):
            self._call_tool_handler = fn
            return fn

        return decorator

    def create_initialization_options(self):
        return {"init": True}


# Build stub modules
_mcp_pkg = types.ModuleType("mcp")
_mcp_server_pkg = types.ModuleType("mcp.server")
_mcp_stdio_pkg = types.ModuleType("mcp.server.stdio")
_mcp_types_pkg = types.ModuleType("mcp.types")

_mcp_types_pkg.TextContent = _FakeTextContent  # type: ignore[attr-defined]
_mcp_types_pkg.Tool = _FakeTool  # type: ignore[attr-defined]
_mcp_server_pkg.Server = _FakeServer  # type: ignore[attr-defined]
_mcp_pkg.server = _mcp_server_pkg  # type: ignore[attr-defined]
_mcp_pkg.types = _mcp_types_pkg  # type: ignore[attr-defined]

sys.modules.setdefault("mcp", _mcp_pkg)
sys.modules.setdefault("mcp.server", _mcp_server_pkg)
sys.modules.setdefault("mcp.server.stdio", _mcp_stdio_pkg)
sys.modules.setdefault("mcp.types", _mcp_types_pkg)

# Now safe to import the server module.
from chromatic_mcp import server as srv  # noqa: E402
from chromatic_mcp.handlers import list_tool_specs  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stdio_context(read_stream=None, write_stream=None):
    """Return an async context manager that yields (read_stream, write_stream)."""
    rs = read_stream or AsyncMock()
    ws = write_stream or AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield rs, ws

    return _ctx()


# ---------------------------------------------------------------------------
# SERVER_NAME constant
# ---------------------------------------------------------------------------


class TestServerName:
    def test_server_name_is_chromatic_harness(self) -> None:
        assert srv.SERVER_NAME == "chromatic-harness"

    def test_server_name_is_str(self) -> None:
        assert isinstance(srv.SERVER_NAME, str)


# ---------------------------------------------------------------------------
# Module import state — _IMPORT_ERROR should be None when stubs are present
# ---------------------------------------------------------------------------


class TestImportState:
    def test_import_error_is_none(self) -> None:
        assert srv._IMPORT_ERROR is None

    def test_server_class_is_not_none(self) -> None:
        assert srv.Server is not None

    def test_stdio_server_is_not_none(self) -> None:
        assert srv.stdio_server is not None

    def test_types_module_is_not_none(self) -> None:
        assert srv.types is not None


# ---------------------------------------------------------------------------
# run_stdio raises RuntimeError when MCP is absent
# ---------------------------------------------------------------------------


class TestRunStdioNoMcp:
    def test_run_stdio_raises_runtime_error_when_server_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(srv, "Server", None)
        monkeypatch.setattr(srv, "stdio_server", None)
        with pytest.raises(RuntimeError, match="mcp package required"):
            asyncio.run(srv.run_stdio())

    def test_run_stdio_error_message_mentions_install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(srv, "Server", None)
        monkeypatch.setattr(srv, "stdio_server", None)
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(srv.run_stdio())
        assert "pip install" in str(exc_info.value) or "mcp" in str(exc_info.value)

    def test_run_stdio_raises_when_only_server_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(srv, "Server", None)
        with pytest.raises(RuntimeError):
            asyncio.run(srv.run_stdio())

    def test_run_stdio_raises_when_only_stdio_server_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(srv, "stdio_server", None)
        with pytest.raises(RuntimeError):
            asyncio.run(srv.run_stdio())


# ---------------------------------------------------------------------------
# _build_server — server construction and handler registration
# ---------------------------------------------------------------------------


class TestBuildServer:
    def test_build_server_returns_server_instance(self) -> None:
        server = srv._build_server()
        assert isinstance(server, _FakeServer)

    def test_build_server_uses_server_name(self) -> None:
        server = srv._build_server()
        assert server.name == srv.SERVER_NAME

    def test_build_server_registers_list_tools_handler(self) -> None:
        server = srv._build_server()
        assert server._list_tools_handler is not None
        assert callable(server._list_tools_handler)

    def test_build_server_registers_call_tool_handler(self) -> None:
        server = srv._build_server()
        assert server._call_tool_handler is not None
        assert callable(server._call_tool_handler)

    def test_build_server_each_call_returns_fresh_instance(self) -> None:
        s1 = srv._build_server()
        s2 = srv._build_server()
        assert s1 is not s2


# ---------------------------------------------------------------------------
# handle_list_tools — async handler registered on server
# ---------------------------------------------------------------------------


class TestHandleListTools:
    @pytest.mark.asyncio
    async def test_list_tools_returns_list(self) -> None:
        server = srv._build_server()
        result = await server._list_tools_handler()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_tools_returns_tool_objects(self) -> None:
        server = srv._build_server()
        result = await server._list_tools_handler()
        for item in result:
            assert isinstance(item, _FakeTool)

    @pytest.mark.asyncio
    async def test_list_tools_count_matches_list_tool_specs(self) -> None:
        server = srv._build_server()
        result = await server._list_tools_handler()
        specs = list_tool_specs()
        assert len(result) == len(specs)

    @pytest.mark.asyncio
    async def test_list_tools_names_match_specs(self) -> None:
        server = srv._build_server()
        result = await server._list_tools_handler()
        spec_names = {s["name"] for s in list_tool_specs()}
        tool_names = {t.name for t in result}
        assert tool_names == spec_names

    @pytest.mark.asyncio
    async def test_list_tools_descriptions_populated(self) -> None:
        server = srv._build_server()
        result = await server._list_tools_handler()
        for tool in result:
            assert tool.description
            assert isinstance(tool.description, str)

    @pytest.mark.asyncio
    async def test_list_tools_input_schema_populated(self) -> None:
        server = srv._build_server()
        result = await server._list_tools_handler()
        for tool in result:
            assert isinstance(tool.inputSchema, dict)
            assert "type" in tool.inputSchema

    @pytest.mark.asyncio
    async def test_list_tools_uses_spec_data(self) -> None:
        """Each tool's name/description/inputSchema must come from list_tool_specs."""
        server = srv._build_server()
        result = await server._list_tools_handler()
        specs = {s["name"]: s for s in list_tool_specs()}
        for tool in result:
            spec = specs[tool.name]
            assert tool.description == spec["description"]
            assert tool.inputSchema == spec["inputSchema"]


# ---------------------------------------------------------------------------
# handle_call_tool — async handler registered on server
# ---------------------------------------------------------------------------


class TestHandleCallTool:
    @pytest.mark.asyncio
    async def test_call_tool_returns_list(self) -> None:
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = await server._call_tool_handler("workflow_go", {"mode": "GO"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_call_tool_returns_text_content(self) -> None:
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = await server._call_tool_handler("workflow_go", {"mode": "GO"})
        assert len(result) == 1
        assert isinstance(result[0], _FakeTextContent)

    @pytest.mark.asyncio
    async def test_call_tool_text_content_type_is_text(self) -> None:
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = await server._call_tool_handler("workflow_go", {})
        assert result[0].type == "text"

    @pytest.mark.asyncio
    async def test_call_tool_text_is_valid_json(self) -> None:
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = await server._call_tool_handler("workflow_go", {"mode": "GO"})
        # The text field must be valid JSON
        parsed = json.loads(result[0].text)
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_call_tool_json_contains_ok_key(self) -> None:
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = await server._call_tool_handler("workflow_go", {"mode": "GO"})
        parsed = json.loads(result[0].text)
        assert "ok" in parsed

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool_returns_error_json(self) -> None:
        server = srv._build_server()
        result = await server._call_tool_handler("no_such_tool", {})
        parsed = json.loads(result[0].text)
        assert parsed["ok"] is False
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_call_tool_none_arguments_handled_safely(self) -> None:
        """Passing None as arguments must not raise — call_tool handles it."""
        server = srv._build_server()
        result = await server._call_tool_handler("no_such_tool", None)
        parsed = json.loads(result[0].text)
        assert parsed["ok"] is False

    @pytest.mark.asyncio
    async def test_call_tool_json_indented(self) -> None:
        """json.dumps with indent=2 should produce multi-line output."""
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = await server._call_tool_handler("workflow_go", {})
        text = result[0].text
        # An indented JSON dump of a non-trivial dict will contain newlines
        assert "\n" in text

    @pytest.mark.asyncio
    async def test_call_tool_non_ascii_preserved(self) -> None:
        """ensure_ascii=False means non-ASCII chars are kept verbatim."""
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.call_tool") as mock_ct:
            mock_ct.return_value = {"ok": True, "message": "héllo wörld"}
            result = await server._call_tool_handler("anything", {})
        assert "héllo wörld" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_delegates_to_call_tool_function(self) -> None:
        """handle_call_tool must pass name and arguments through to handlers.call_tool."""
        server = srv._build_server()
        with patch("chromatic_mcp.handlers.call_tool") as mock_ct:
            mock_ct.return_value = {"ok": True}
            await server._call_tool_handler("beads_ready", {"arg": "val"})
        mock_ct.assert_called_once_with("beads_ready", {"arg": "val"})


# ---------------------------------------------------------------------------
# run_stdio lifecycle — when MCP stubs are available
# ---------------------------------------------------------------------------


class TestRunStdioLifecycle:
    @pytest.mark.asyncio
    async def test_run_stdio_calls_server_run(self) -> None:
        """run_stdio must await server.run(read_stream, write_stream, init_opts)."""
        fake_server = _FakeServer(srv.SERVER_NAME)
        fake_server.run = AsyncMock()

        async def _fake_stdio():
            rs = AsyncMock()
            ws = AsyncMock()
            yield rs, ws

        with (
            patch.object(srv, "_build_server", return_value=fake_server),
            patch.object(srv, "stdio_server", new=_fake_stdio),
        ):
            await srv.run_stdio()

        fake_server.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_stdio_passes_streams_to_server_run(self) -> None:
        """server.run must receive the read and write streams from stdio_server."""
        fake_server = _FakeServer(srv.SERVER_NAME)
        fake_server.run = AsyncMock()
        rs_sentinel = object()
        ws_sentinel = object()

        async def _fake_stdio():
            yield rs_sentinel, ws_sentinel

        with (
            patch.object(srv, "_build_server", return_value=fake_server),
            patch.object(srv, "stdio_server", new=_fake_stdio),
        ):
            await srv.run_stdio()

        call_args = fake_server.run.call_args
        assert call_args[0][0] is rs_sentinel
        assert call_args[0][1] is ws_sentinel

    @pytest.mark.asyncio
    async def test_run_stdio_passes_init_options(self) -> None:
        """The third argument to server.run must be create_initialization_options()."""
        fake_server = _FakeServer(srv.SERVER_NAME)
        fake_server.run = AsyncMock()
        expected_opts = {"init": True}  # matches _FakeServer.create_initialization_options

        async def _fake_stdio():
            yield AsyncMock(), AsyncMock()

        with (
            patch.object(srv, "_build_server", return_value=fake_server),
            patch.object(srv, "stdio_server", new=_fake_stdio),
        ):
            await srv.run_stdio()

        call_args = fake_server.run.call_args
        assert call_args[0][2] == expected_opts

    @pytest.mark.asyncio
    async def test_run_stdio_calls_build_server(self) -> None:
        """run_stdio must call _build_server() exactly once."""
        fake_server = _FakeServer(srv.SERVER_NAME)
        fake_server.run = AsyncMock()

        async def _fake_stdio():
            yield AsyncMock(), AsyncMock()

        with (
            patch.object(srv, "_build_server", return_value=fake_server) as mock_build,
            patch.object(srv, "stdio_server", new=_fake_stdio),
        ):
            await srv.run_stdio()

        mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# main() — synchronous entry point
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_calls_asyncio_run(self) -> None:
        """main() must call asyncio.run with a coroutine from run_stdio."""
        with patch("chromatic_mcp.server.asyncio") as mock_asyncio:
            srv.main()
        mock_asyncio.run.assert_called_once()

    def test_main_passes_run_stdio_coroutine(self) -> None:
        """The argument passed to asyncio.run must be a coroutine from run_stdio."""
        captured_arg = {}

        def _capture_run(coro):
            captured_arg["coro"] = coro
            # Close the coroutine to avoid ResourceWarning
            coro.close()

        with patch("chromatic_mcp.server.asyncio") as mock_asyncio:
            mock_asyncio.run.side_effect = _capture_run
            srv.main()

        assert "coro" in captured_arg
        # The coroutine's qualified name should reference run_stdio
        assert "run_stdio" in captured_arg["coro"].__qualname__

    def test_main_is_callable(self) -> None:
        assert callable(srv.main)
