"""Windows-safe bd invocation: _bd_argv resolves the bd.CMD shim or falls back to `cmd /c`.

Regression for the bare ``subprocess.run(["bd", ...])`` pattern, which raises
FileNotFoundError on Windows (CreateProcess ignores PATHEXT for a bare spawn),
making `bd prime` silently never run.
"""

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("session_start", _REPO / "scripts" / "session_start.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)  # type: ignore


def test_bd_argv_uses_resolved_path_when_found(monkeypatch):
    monkeypatch.setattr(ss.shutil, "which", lambda name: r"C:\npm\bd.CMD")
    argv = ss._bd_argv(["prime"])
    # The resolved absolute path is executed, not the bare name.
    assert argv == [r"C:\npm\bd.CMD", "prime"]
    assert argv[0] != "bd"


def test_bd_argv_falls_back_to_cmd_when_not_found(monkeypatch):
    monkeypatch.setattr(ss.shutil, "which", lambda name: None)
    assert ss._bd_argv(["ready"]) == ["cmd", "/c", "bd", "ready"]


def test_bd_helper_routes_through_bd_argv(monkeypatch):
    captured = {}

    def fake_run_safe(cmd, cwd=None, timeout=20):
        captured["cmd"] = cmd

        class R:
            returncode = 0
            stdout = "ok"

        return R()

    monkeypatch.setattr(ss.shutil, "which", lambda name: "/usr/bin/bd")
    monkeypatch.setattr(ss, "run_safe", fake_run_safe)
    code, out = ss._bd(["ready"])
    assert code == 0 and out == "ok"
    assert captured["cmd"] == ["/usr/bin/bd", "ready"]
