"""Resolve GitKraken CLI (gk) for subprocess calls — Windows-safe."""

from __future__ import annotations

import os
import shutil


def resolve_gk_argv() -> list[str]:
    """Return argv prefix to invoke `gk` (full path on Windows when needed)."""
    if os.name == "nt":
        for name in ("gk.cmd", "gk.exe", "gk"):
            path = shutil.which(name)
            if path:
                return [path]
    else:
        path = shutil.which("gk")
        if path:
            return [path]
    return ["gk"]
