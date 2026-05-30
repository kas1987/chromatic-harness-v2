"""Git/gh argv resolution — optional GitKraken CLI (gk) passthrough for git ops."""

from __future__ import annotations

import os
import shutil
import subprocess

from intake.gk_runner import resolve_gk_argv

VALID_BACKENDS = frozenset({"auto", "gk", "git"})


def git_backend_name() -> str:
    raw = os.environ.get("CHROMATIC_GIT_BACKEND", "auto").strip().lower()
    return raw if raw in VALID_BACKENDS else "auto"


def gk_available() -> bool:
    argv = resolve_gk_argv()
    try:
        proc = subprocess.run(
            argv + ["version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def active_git_backend() -> str:
    """Return backend that git_argv will use: 'gk' or 'git'."""
    backend = git_backend_name()
    if backend == "git":
        return "git"
    if backend == "gk":
        return "gk" if gk_available() else "git"
    return "gk" if gk_available() else "git"


def git_argv(*args: str) -> list[str]:
    """Build argv for a git subcommand (via gk passthrough when enabled)."""
    if active_git_backend() == "gk":
        return resolve_gk_argv() + list(args)
    return ["git", *args]


def gh_argv(*args: str) -> list[str]:
    """Build argv for gh — always native gh (gk pr create not used by harness pipeline)."""
    if os.name == "nt":
        for name in ("gh.exe", "gh.cmd", "gh"):
            path = shutil.which(name)
            if path:
                return [path, *args]
    else:
        path = shutil.which("gh")
        if path:
            return [path, *args]
    return ["gh", *args]
