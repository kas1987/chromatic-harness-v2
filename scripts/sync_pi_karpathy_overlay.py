#!/usr/bin/env python3
"""Copy harness Karpathy discipline overlay into roach-pi submodule."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OVERLAY = REPO / "02_RUNTIME" / "pi" / "overlays" / "discipline.ts"
TARGET = (
    REPO
    / "02_RUNTIME"
    / "runtime-engines"
    / "roach-pi"
    / "extensions"
    / "agentic-harness"
    / "discipline.ts"
)


def sync(*, quiet: bool = False) -> bool:
    if not OVERLAY.is_file():
        print(f"Missing overlay: {OVERLAY}", file=sys.stderr)
        return False
    if not TARGET.parent.is_dir():
        if not quiet:
            print(f"Skip: roach-pi submodule not checked out ({TARGET.parent})")
        return False
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OVERLAY, TARGET)
    if not quiet:
        print(f"Synced {OVERLAY.name} -> {TARGET.relative_to(REPO)}")
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Sync Pi Karpathy discipline overlay")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    return 0 if sync(quiet=args.quiet) else 1


if __name__ == "__main__":
    raise SystemExit(main())
