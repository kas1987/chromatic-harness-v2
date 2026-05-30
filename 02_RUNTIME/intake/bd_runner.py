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
