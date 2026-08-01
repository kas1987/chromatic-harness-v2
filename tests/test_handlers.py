"""Tests for 02_RUNTIME/chromatic_mcp/handlers.py — MCP tool handler routing.

Uses importlib.util.spec_from_file_location to load the module.
All subprocess calls are patched — no real scripts are executed.
Tests verify handler routing logic: correct script invocation, argument
construction, flag propagation, and call_tool dispatch/error handling.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub MCP SDK so server.py (sibling) can be imported if needed.
# ---------------------------------------------------------------------------
for _mod in ("mcp", "mcp.server", "mcp.server.stdio", "mcp.types"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from chromatic_mcp.handlers import (  # noqa: E402
    HANDLERS,
    _run_script,
    _session_id,
    auto_intake,
    beads_ready,
    call_tool,
    cat_sync_intake,
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
# Helpers
# ---------------------------------------------------------------------------


def _mock_proc(returncode: int = 0, stdout: str = "{}", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# TestHandlers
# ---------------------------------------------------------------------------


class TestHandlers:
    # ------------------------------------------------------------------
    # _session_id helper
    # ------------------------------------------------------------------

    def test_session_id_returns_stripped_non_empty_input(self):
        assert _session_id("  my-session  ") == "my-session"

    def test_session_id_none_falls_back_to_nonempty_string(self):
        sid = _session_id(None)
        assert isinstance(sid, str)
        assert sid  # must be non-empty

    def test_session_id_empty_string_falls_back(self):
        sid = _session_id("")
        assert isinstance(sid, str)
        assert sid

    def test_session_id_reads_file_when_none_and_file_exists(self, tmp_path):
        session_file = tmp_path / ".agents" / "handoffs" / "cursor_session_id.txt"
        session_file.parent.mkdir(parents=True)
        session_file.write_text("file-session-xyz\n", encoding="utf-8")
        with patch("chromatic_mcp.handlers.REPO_ROOT", tmp_path):
            sid = _session_id(None)
        assert sid == "file-session-xyz"

    def test_session_id_anonymous_when_file_missing(self, tmp_path):
        with patch("chromatic_mcp.handlers.REPO_ROOT", tmp_path):
            sid = _session_id(None)
        assert sid == "anonymous-session"

    # ------------------------------------------------------------------
    # list_tool_specs
    # ------------------------------------------------------------------

    def test_list_tool_specs_returns_list(self):
        specs = list_tool_specs()
        assert isinstance(specs, list)
        assert len(specs) >= 8

    def test_list_tool_specs_all_have_name_description_schema(self):
        for spec in list_tool_specs():
            assert "name" in spec
            assert "description" in spec
            assert "inputSchema" in spec

    def test_list_tool_specs_contains_expected_tools(self):
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
            "cat_sync_intake",
        ]:
            assert expected in names, f"missing spec: {expected}"

    def test_list_tool_specs_workflow_go_has_mode_property(self):
        specs = {s["name"]: s for s in list_tool_specs()}
        assert "mode" in specs["workflow_go"]["inputSchema"]["properties"]

    def test_list_tool_specs_session_guard_has_surface_and_force(self):
        specs = {s["name"]: s for s in list_tool_specs()}
        props = specs["session_guard"]["inputSchema"]["properties"]
        assert "surface" in props
        assert "force" in props

    # ------------------------------------------------------------------
    # call_tool — unknown tool denial
    # ------------------------------------------------------------------

    def test_call_tool_unknown_tool_returns_ok_false(self):
        result = call_tool("does_not_exist", {})
        assert result["ok"] is False

    def test_call_tool_unknown_tool_error_message(self):
        result = call_tool("does_not_exist", {})
        assert "unknown tool" in result["error"]

    def test_call_tool_none_arguments_safe(self):
        result = call_tool("does_not_exist", None)
        assert result["ok"] is False

    # ------------------------------------------------------------------
    # Handler routing — workflow_go
    # ------------------------------------------------------------------

    def test_call_tool_workflow_go_dispatches_go_script(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            result = call_tool("workflow_go", {"mode": "GO"})
        assert result["ok"] is True
        cmd = mock_run.call_args[0][0]
        assert "workflow_go.py" in str(cmd)

    def test_call_tool_workflow_go_default_mode_go(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("workflow_go", {})
        cmd = mock_run.call_args[0][0]
        assert "GO" in cmd

    # ------------------------------------------------------------------
    # Handler routing — workflow_git_ship (dry_run flag)
    # ------------------------------------------------------------------

    def test_call_tool_workflow_git_ship_dry_run_excludes_execute(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("workflow_git_ship", {"dry_run": True})
        cmd = mock_run.call_args[0][0]
        assert "--execute" not in cmd

    def test_call_tool_workflow_git_ship_not_dry_run_includes_execute(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("workflow_git_ship", {"dry_run": False})
        cmd = mock_run.call_args[0][0]
        assert "--execute" in cmd

    # ------------------------------------------------------------------
    # Handler routing — auto_intake
    # ------------------------------------------------------------------

    def test_call_tool_auto_intake_dry_run_flag(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("auto_intake", {"dry_run": True})
        cmd = mock_run.call_args[0][0]
        assert "--dry-run" in cmd

    def test_call_tool_auto_intake_limit_arg(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("auto_intake", {"limit": 5})
        cmd = mock_run.call_args[0][0]
        assert "--limit" in cmd
        assert "5" in cmd

    # ------------------------------------------------------------------
    # Handler routing — poll_inbox
    # ------------------------------------------------------------------

    def test_call_tool_poll_inbox_passes_limit(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("poll_inbox", {"limit": 10})
        cmd = mock_run.call_args[0][0]
        assert "--limit" in cmd
        assert "10" in cmd

    def test_call_tool_poll_inbox_dry_run_flag(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("poll_inbox", {"dry_run": True})
        cmd = mock_run.call_args[0][0]
        assert "--dry-run" in cmd

    # ------------------------------------------------------------------
    # Handler routing — parallel_health
    # ------------------------------------------------------------------

    def test_call_tool_parallel_health_no_prune_flag_absent(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("parallel_health", {"prune": False})
        cmd = mock_run.call_args[0][0]
        assert "--prune" not in cmd

    def test_call_tool_parallel_health_prune_flag_present(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("parallel_health", {"prune": True})
        cmd = mock_run.call_args[0][0]
        assert "--prune" in cmd

    # ------------------------------------------------------------------
    # Handler routing — session_guard (security: force flag must be explicit)
    # ------------------------------------------------------------------

    def test_call_tool_session_guard_defaults_surface_mcp(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("session_guard", {})
        cmd = mock_run.call_args[0][0]
        assert "--surface" in cmd
        assert "mcp" in cmd

    def test_call_tool_session_guard_force_only_when_explicitly_set(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("session_guard", {})
        cmd = mock_run.call_args[0][0]
        assert "--force" not in cmd, "force must not appear when not requested"

    def test_call_tool_session_guard_force_flag_when_requested(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("session_guard", {"force": True})
        cmd = mock_run.call_args[0][0]
        assert "--force" in cmd

    def test_call_tool_session_guard_dry_run_flag(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("session_guard", {"dry_run": True})
        cmd = mock_run.call_args[0][0]
        assert "--dry-run" in cmd

    def test_call_tool_session_guard_full_flag(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("session_guard", {"full": True})
        cmd = mock_run.call_args[0][0]
        assert "--full" in cmd

    # ------------------------------------------------------------------
    # Handler routing — check_operations, validate_intake_loop
    # ------------------------------------------------------------------

    def test_call_tool_check_agent_operations_script(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("check_agent_operations", {})
        cmd = mock_run.call_args[0][0]
        assert "check_agent_operations.py" in str(cmd)

    def test_call_tool_validate_intake_loop_script(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("validate_intake_loop", {})
        cmd = mock_run.call_args[0][0]
        assert "validate_intake_loop.py" in str(cmd)

    # ------------------------------------------------------------------
    # Handler routing — cat_sync_intake
    # ------------------------------------------------------------------

    def test_call_tool_cat_sync_intake_dry_run(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("cat_sync_intake", {"dry_run": True})
        cmd = mock_run.call_args[0][0]
        assert "--dry-run" in cmd

    def test_call_tool_cat_sync_intake_no_dry_run(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc()) as mock_run:
            call_tool("cat_sync_intake", {"dry_run": False})
        cmd = mock_run.call_args[0][0]
        assert "--dry-run" not in cmd

    # ------------------------------------------------------------------
    # call_tool — subprocess failure and exception handling
    # ------------------------------------------------------------------

    def test_call_tool_subprocess_failure_inner_result_ok_false(self):
        with patch(
            "chromatic_mcp.handlers.subprocess.run",
            return_value=_mock_proc(returncode=1, stderr="error"),
        ):
            result = call_tool("workflow_go", {"mode": "GO"})
        assert result["ok"] is True  # outer dispatch succeeded
        assert result["result"]["ok"] is False  # script returned non-zero

    def test_call_tool_handler_exception_returns_ok_false(self):
        with patch.dict(HANDLERS, {"boom": lambda _: (_ for _ in ()).throw(RuntimeError("kaboom"))}):
            result = call_tool("boom", {})
        assert result["ok"] is False
        assert "kaboom" in result["error"]

    # ------------------------------------------------------------------
    # _run_script — truncation and exit code
    # ------------------------------------------------------------------

    def test_run_script_stdout_truncated_to_8000(self):
        long_out = "x" * 20000
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc(stdout=long_out)):
            result = _run_script("dummy.py")
        assert len(result["stdout"]) <= 8000

    def test_run_script_stderr_truncated_to_2000(self):
        long_err = "e" * 5000
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc(stderr=long_err)):
            result = _run_script("dummy.py")
        assert len(result["stderr"]) <= 2000

    def test_run_script_returns_exit_code(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc(returncode=42)):
            result = _run_script("dummy.py")
        assert result["exit_code"] == 42

    def test_run_script_ok_true_on_zero_exit(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc(returncode=0)):
            result = _run_script("dummy.py")
        assert result["ok"] is True

    def test_run_script_ok_false_on_nonzero_exit(self):
        with patch("chromatic_mcp.handlers.subprocess.run", return_value=_mock_proc(returncode=1)):
            result = _run_script("dummy.py")
        assert result["ok"] is False

    # ------------------------------------------------------------------
    # HANDLERS dict completeness
    # ------------------------------------------------------------------

    def test_handlers_dict_contains_all_expected_keys(self):
        expected = {
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
            "cat_sync_intake",
        }
        for key in expected:
            assert key in HANDLERS, f"HANDLERS missing: {key}"

    def test_handlers_dict_values_are_callable(self):
        for name, fn in HANDLERS.items():
            assert callable(fn), f"HANDLERS[{name!r}] is not callable"
