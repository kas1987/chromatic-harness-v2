"""Resolve beads CLI (bd) for subprocess calls — Windows-safe."""

from __future__ import annotations

import os
import shutil


def resolve_bd_argv() -> list[str]:
    """Return argv prefix to invoke `bd` (full path on Windows when needed)."""
    if os.name == "nt":
        for name in ("bd.cmd", "bd.exe", "bd"):
            path = shutil.which(name)
            if path:
                return [path]
    else:
        path = shutil.which("bd")
        if path:
            return [path]
    return ["bd"]


def bd_available() -> bool:
    """True when a `bd` executable is resolvable on this environment's PATH.

    Used to distinguish a real beads failure from an environment that simply
    has no beads CLI installed (cloud/CI/fresh container), so callers can
    degrade gracefully instead of treating absence as failure.
    """
    if os.name == "nt":
        return any(shutil.which(name) for name in ("bd.cmd", "bd.exe", "bd"))
    return shutil.which("bd") is not None
