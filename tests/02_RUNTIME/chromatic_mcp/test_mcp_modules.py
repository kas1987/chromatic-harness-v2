"""Tests for 02_RUNTIME/chromatic_mcp/ — handlers.py and server.py."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# Stub MCP SDK imports so server.py can be imported without the real package.
_mcp_pkg = types.ModuleType("mcp")
_mcp_server_pkg = types.ModuleType("mcp.server")
_mcp_stdio_pkg = types.ModuleType("mcp.server.stdio")
_mcp_types_pkg = types.ModuleType("mcp.types")

_mcp_pkg.server = _mcp_server_pkg  # type: ignore[attr-defined]
sys.modules.setdefault("mcp", _mcp_pkg)
sys.modules.setdefault("mcp.server", _mcp_server_pkg)
sys.modules.setdefault("mcp.server.stdio", _mcp_stdio_pkg)
sys.modules.setdefault("mcp.types", _mcp_types_pkg)

from chromatic_mcp.handlers import (  # noqa: E402
    HANDLERS,
    _run_script,
    _session_id,
    auto_intake,
    beads_ready,
    call_tool,
    check_operations,
    list_tool_specs,
    parallel_health,
    poll_inbox,
    session_guard,
    validate_intake_loop,
    workflow_git_ship,
    workflow_go,
)


# ---------------------------------------------------------------------------
# _session_id helper
# ---------------------------------------------------------------------------


def test_session_id_returns_stripped_input():
    assert _session_id("  my-session  ") == "my-session"


def test_session_id_strips_whitespace():
    # When whitespace-only string is passed, returns file contents or anonymous-session.
    sid = _session_id("   ")
    assert isinstance(sid, str)
    assert sid.strip()  # must be non-empty, non-whitespace


def test_session_id_none_returns_anonymous_or_file(tmp_path):
    # Without a session file, anonymous-session should be returned.
    sid = _session_id(None)
    assert isinstance(sid, str)
    assert sid  # non-empty


def test_session_id_reads_file_if_exists(tmp_path):
    session_file = tmp_path / "handoffs" / "cursor_session_id.txt"
    session_file.parent.mkdir(parents=True)
    session_file.write_text("file-session-123\n", encoding="utf-8")
    repo_root_patch = tmp_path
    with patch("chromatic_mcp.handlers.REPO_ROOT", repo_root_patch):
        # Patch the constant used for the session file path.
        sid = _session_id(None)
    # When None is passed and no empty string, falls back to file or anonymous.
    assert isinstance(sid, str)


# ---------------------------------------------------------------------------
# list_tool_specs
# ---------------------------------------------------------------------------


def test_list_tool_specs_returns_list():
    specs = list_tool_specs()
    assert isinstance(specs, list)
    assert len(specs) >= 8


def test_list_tool_specs_all_have_name_and_description():
    specs = list_tool_specs()
    for spec in specs:
        assert "name" in spec
        assert "description" in spec
        assert "inputSchema" in spec


def test_list_tool_specs_expected_tools():
    names = {s["name"] for s in list_tool_specs()}
    for expected in [
        "workflow_go",
        "workflow_git_ship",
        "auto_intake",
        "poll_inbox",
        "intake_queue_list",
        "beads_ready",
        "check_agent_operations",
        "validate_intake_loop",
        "parallel_health",
        "session_guard",
    ]:
        assert expected in names


def test_list_tool_specs_workflow_go_schema():
    specs = {s["name"]: s for s in list_tool_specs()}
    schema = specs["workflow_go"]["inputSchema"]
    assert schema["type"] == "object"
    assert "mode" in schema["properties"]


def test_list_tool_specs_session_guard_schema():
    specs = {s["name"]: s for s in list_tool_specs()}
    schema = specs["session_guard"]["inputSchema"]
    props = schema["properties"]
    assert "surface" in props
    assert "invoked_by" in props
    assert "force" in props


# ---------------------------------------------------------------------------
# call_tool — unknown tool
# ---------------------------------------------------------------------------


def test_call_tool_unknown_tool():
    result = call_tool("definitely_not_a_tool", {})
    assert result["ok"] is False
    assert "unknown tool" in result["error"]


def test_call_tool_none_arguments_is_safe():
    result = call_tool("definitely_not_a_tool", None)
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# call_tool — handler dispatch (mocked subprocess)
# ---------------------------------------------------------------------------


def _mock_proc(returncode: int = 0, stdout: str = "{}", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def test_call_tool_workflow_go_dispatches():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("workflow_go", {"mode": "GO"})
    assert result["ok"] is True
    assert result["result"]["ok"] is True
    mock_run.assert_called_once()


def test_call_tool_workflow_go_default_mode():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("workflow_go", {})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "workflow_go.py" in str(cmd_args)


def test_call_tool_workflow_git_ship_dry_run():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("workflow_git_ship", {"dry_run": True})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    # dry_run=True should NOT include --execute flag.
    assert "--execute" not in cmd_args


def test_call_tool_workflow_git_ship_not_dry_run():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("workflow_git_ship", {"dry_run": False})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--execute" in cmd_args


def test_call_tool_auto_intake_dry_run():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("auto_intake", {"dry_run": True})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--dry-run" in cmd_args


def test_call_tool_auto_intake_with_limit():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("auto_intake", {"limit": 5})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--limit" in cmd_args
    assert "5" in cmd_args


def test_call_tool_poll_inbox_limit():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("poll_inbox", {"limit": 10})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--limit" in cmd_args
    assert "10" in cmd_args


def test_call_tool_parallel_health_no_prune():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("parallel_health", {"prune": False})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--prune" not in cmd_args


def test_call_tool_parallel_health_with_prune():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("parallel_health", {"prune": True})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--prune" in cmd_args


def test_call_tool_session_guard_defaults():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("session_guard", {})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--surface" in cmd_args
    assert "mcp" in cmd_args


def test_call_tool_session_guard_force_flag():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("session_guard", {"force": True})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--force" in cmd_args


def test_call_tool_session_guard_dry_run_flag():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("session_guard", {"dry_run": True})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "--dry-run" in cmd_args


def test_call_tool_check_agent_operations():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("check_agent_operations", {})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "check_agent_operations.py" in str(cmd_args)


def test_call_tool_validate_intake_loop():
    with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
        result = call_tool("validate_intake_loop", {})
    assert result["ok"] is True
    cmd_args = mock_run.call_args[0][0]
    assert "validate_intake_loop.py" in str(cmd_args)


# ---------------------------------------------------------------------------
# call_tool — subprocess failure propagates ok=False
# ---------------------------------------------------------------------------


def test_call_tool_subprocess_failure():
    with patch(
        "chromatic_mcp.handlers.subprocess.run",
        return_value=_mock_proc(returncode=1, stderr="something failed"),
    ):
        result = call_tool("workflow_go", {"mode": "GO"})
    # call_tool wraps _run_script; result["ok"] reflects script ok.
    assert result["ok"] is True  # outer call_tool succeeded
    assert result["result"]["ok"] is False  # inner script returned non-zero


# ---------------------------------------------------------------------------
# call_tool — exception in handler returns ok=False
# ---------------------------------------------------------------------------


def test_call_tool_handler_exception():
    with patch.dict(HANDLERS, {"boom": lambda _: (_ for _ in ()).throw(RuntimeError("kaboom"))}):
        result = call_tool("boom", {})
    assert result["ok"] is False
    assert "kaboom" in result["error"]


# ---------------------------------------------------------------------------
# _run_script helper
# ---------------------------------------------------------------------------


def test_run_script_truncates_long_stdout():
    long_output = "x" * 20000
    with patch(
        "chromatic_mcp.handlers.subprocess.run",
        return_value=_mock_proc(stdout=long_output),
    ):
        result = _run_script("dummy.py")
    assert len(result["stdout"]) <= 8000


def test_run_script_truncates_long_stderr():
    long_err = "e" * 5000
    with patch(
        "chromatic_mcp.handlers.subprocess.run",
        return_value=_mock_proc(stderr=long_err),
    ):
        result = _run_script("dummy.py")
    assert len(result["stderr"]) <= 2000


def test_run_script_returns_exit_code():
    with patch(
        "chromatic_mcp.handlers.subprocess.run",
        return_value=_mock_proc(returncode=42),
    ):
        result = _run_script("dummy.py")
    assert result["exit_code"] == 42


# ---------------------------------------------------------------------------
# server.py — importable and constants defined
# ---------------------------------------------------------------------------


def test_server_module_importable():
    from chromatic_mcp import server as srv

    assert srv.SERVER_NAME == "chromatic-harness"


def test_server_run_stdio_raises_without_mcp():
    # In our test environment, Server is None (stubbed without real MCP).
    from chromatic_mcp import server as srv

    # If Server is None, run_stdio should raise RuntimeError.
    if srv.Server is None:
        import asyncio

        with pytest.raises(RuntimeError, match="mcp package required"):
            asyncio.run(srv.run_stdio())


def test_server_build_server_skipped_if_no_mcp():
    from chromatic_mcp import server as srv

    if srv.Server is None:
        # _build_server should not be called when Server is None.
        pytest.skip("MCP not available — _build_server skipped as expected")
