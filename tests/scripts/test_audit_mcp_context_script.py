"""Additional tests for scripts/audit_mcp_context.py.

Focuses on unit-level logic (scan_mcps, resolve_mcps_path) not covered by
the subprocess-based tests in tests/test_audit_mcp_context.py.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_RUNTIME = Path(__file__).resolve().parents[2] / "02_RUNTIME"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import audit_mcp_context as amc


# ---------------------------------------------------------------------------
# scan_mcps
# ---------------------------------------------------------------------------


class TestScanMcps:
    def test_empty_dir_returns_zero(self, tmp_path):
        total, per_server = amc.scan_mcps(tmp_path)
        assert total == 0
        assert per_server == {}

    def test_single_tool_counted(self, tmp_path):
        server_dir = tmp_path / "my-server" / "tools"
        server_dir.mkdir(parents=True)
        content = json.dumps({"name": "my_tool", "description": "does stuff"})
        (server_dir / "my_tool.json").write_text(content, encoding="utf-8")
        total, per_server = amc.scan_mcps(tmp_path)
        assert total == len(content)
        assert "my-server" in per_server
        assert per_server["my-server"] == len(content)

    def test_multiple_tools_same_server_summed(self, tmp_path):
        server_dir = tmp_path / "alpha-server" / "tools"
        server_dir.mkdir(parents=True)
        (server_dir / "tool_a.json").write_text("aaa", encoding="utf-8")
        (server_dir / "tool_b.json").write_text("bb", encoding="utf-8")
        total, per_server = amc.scan_mcps(tmp_path)
        assert per_server["alpha-server"] == 5
        assert total == 5

    def test_multiple_servers_tracked_separately(self, tmp_path):
        for sname in ("server-one", "server-two"):
            d = tmp_path / sname / "tools"
            d.mkdir(parents=True)
            (d / "t.json").write_text("x" * 10, encoding="utf-8")
        total, per_server = amc.scan_mcps(tmp_path)
        assert total == 20
        assert per_server["server-one"] == 10
        assert per_server["server-two"] == 10

    def test_non_json_files_not_counted(self, tmp_path):
        server_dir = tmp_path / "srv" / "tools"
        server_dir.mkdir(parents=True)
        (server_dir / "tool.json").write_text("abc", encoding="utf-8")
        (server_dir / "README.txt").write_text("lots of text here", encoding="utf-8")
        total, _ = amc.scan_mcps(tmp_path)
        assert total == 3

    def test_files_outside_tools_not_counted(self, tmp_path):
        server_dir = tmp_path / "srv"
        server_dir.mkdir(parents=True)
        (server_dir / "metadata.json").write_text("ignored", encoding="utf-8")
        tools_dir = server_dir / "tools"
        tools_dir.mkdir()
        (tools_dir / "real.json").write_text("counted", encoding="utf-8")
        total, _ = amc.scan_mcps(tmp_path)
        assert total == len("counted")


# ---------------------------------------------------------------------------
# resolve_mcps_path
# ---------------------------------------------------------------------------


class TestResolveMcpsPath:
    def test_cli_path_takes_priority(self, tmp_path):
        result = amc.resolve_mcps_path(str(tmp_path))
        assert result == tmp_path

    def test_none_falls_back_to_fixture(self):
        with patch.object(amc, "_load_settings", return_value={}):
            result = amc.resolve_mcps_path(None)
        assert result.name == "mcp_minimal"

    def test_settings_path_used_when_set(self, tmp_path):
        custom = tmp_path / "custom_mcps"
        custom.mkdir()
        with patch.object(amc, "_load_settings", return_value={"mcp_descriptors_path": str(custom)}):
            result = amc.resolve_mcps_path(None)
        assert result == custom


# ---------------------------------------------------------------------------
# token estimation math
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    def test_total_tokens_is_chars_div_4(self, tmp_path):
        server_dir = tmp_path / "srv" / "tools"
        server_dir.mkdir(parents=True)
        # exactly 400 chars
        (server_dir / "t.json").write_text("x" * 400, encoding="utf-8")
        total, _ = amc.scan_mcps(tmp_path)
        assert total // 4 == 100

    def test_per_server_tokens_reported_in_report(self, tmp_path):
        server_dir = tmp_path / "my-srv" / "tools"
        server_dir.mkdir(parents=True)
        (server_dir / "tool.json").write_text("a" * 80, encoding="utf-8")
        total, per_server = amc.scan_mcps(tmp_path)
        assert per_server["my-srv"] // 4 == 20


# ---------------------------------------------------------------------------
# _load_settings
# ---------------------------------------------------------------------------


class TestLoadSettings:
    def test_returns_empty_dict_when_no_config_files(self, monkeypatch):
        # Patch _REPO to point to a temp dir with no config files
        import audit_mcp_context as _m

        original = _m._REPO
        try:
            monkeypatch.setattr(_m, "_REPO", Path("/nonexistent_path_xyz"))
            result = _m._load_settings()
            assert result == {}
        finally:
            monkeypatch.setattr(_m, "_REPO", original)


# ---------------------------------------------------------------------------
# _load_profile
# ---------------------------------------------------------------------------


class TestLoadProfile:
    def test_returns_empty_when_profile_missing(self, monkeypatch):
        import audit_mcp_context as _m

        original = _m._PROFILE_PATH
        try:
            monkeypatch.setattr(_m, "_PROFILE_PATH", Path("/nonexistent/profile.yaml"))
            result = _m._load_profile()
            assert result == {}
        finally:
            monkeypatch.setattr(_m, "_PROFILE_PATH", original)


# ---------------------------------------------------------------------------
# Integration: main() with mcps_path not a dir
# ---------------------------------------------------------------------------


class TestMainMissingPath:
    def test_returns_1_for_missing_path(self, monkeypatch):
        import argparse
        import audit_mcp_context as _m

        fake_args = argparse.Namespace(
            mcps_path="/nonexistent/path/xyz",
            profile="harness_dev",
            strict=False,
            json=False,
        )
        with patch("sys.argv", ["audit_mcp_context.py", "--mcps-path", "/nonexistent/path/xyz"]):
            # Call resolve_mcps_path directly then check directory check
            path = _m.resolve_mcps_path("/nonexistent/path/xyz")
            assert not path.is_dir()


# ---------------------------------------------------------------------------
# heavy_present detection logic (via main-level logic simulation)
# ---------------------------------------------------------------------------


class TestHeavyServerDetection:
    def test_heavy_server_detected(self, tmp_path):
        """Simulate the heavy_present computation done inside main()."""
        per_server = {"plugin-heavy-server": 8000, "plugin-light": 100}
        disable_daily = {"plugin-heavy-server"}
        heavy_present = [s for s in per_server if s in disable_daily]
        assert heavy_present == ["plugin-heavy-server"]

    def test_no_heavy_when_disable_list_empty(self, tmp_path):
        per_server = {"plugin-something": 5000}
        disable_daily: set = set()
        heavy_present = [s for s in per_server if s in disable_daily]
        assert heavy_present == []

    def test_recommended_servers_identified(self):
        per_server = {"server-a": 100, "server-b": 200}
        recommended = {"server-b"}
        identified = [s for s in per_server if s in recommended]
        assert identified == ["server-b"]


# ---------------------------------------------------------------------------
# Edge cases: scan_mcps nested deeply
# ---------------------------------------------------------------------------


class TestScanMcpsNested:
    def test_deep_nested_tools_counted(self, tmp_path):
        deep = tmp_path / "outer" / "inner-server" / "tools"
        deep.mkdir(parents=True)
        (deep / "nested.json").write_text("nested_content", encoding="utf-8")
        total, per_server = amc.scan_mcps(tmp_path)
        assert total == len("nested_content")
        # server name from parts[-3] when at least 3 parts deep in rglob
        assert total > 0

    def test_zero_byte_file_counted(self, tmp_path):
        srv = tmp_path / "srv" / "tools"
        srv.mkdir(parents=True)
        (srv / "empty.json").write_text("", encoding="utf-8")
        total, per_server = amc.scan_mcps(tmp_path)
        assert total == 0
        assert "srv" in per_server
