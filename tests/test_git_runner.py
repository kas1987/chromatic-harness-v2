from intake.gk_runner import resolve_gk_argv
from workflows.git_runner import active_git_backend, git_argv, git_backend_name


def test_resolve_gk_argv_returns_list():
    argv = resolve_gk_argv()
    assert isinstance(argv, list)
    assert len(argv) >= 1
    assert argv[0]


def test_git_argv_starts_with_git_or_gk():
    cmd = git_argv("status", "--short")
    assert len(cmd) >= 2
    assert cmd[-2:] == ["status", "--short"]
    exe = cmd[0].replace("\\", "/").lower()
    assert exe.endswith("/git") or exe.endswith("/git.exe") or exe.endswith("/gk") or exe.endswith("/gk.exe") or exe in ("git", "gk")


def test_active_git_backend_is_known():
    assert active_git_backend() in ("git", "gk")


def test_git_backend_name_default_auto():
    import os

    old = os.environ.pop("CHROMATIC_GIT_BACKEND", None)
    try:
        assert git_backend_name() == "auto"
    finally:
        if old is not None:
            os.environ["CHROMATIC_GIT_BACKEND"] = old
