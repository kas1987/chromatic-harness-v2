#!/usr/bin/env python3
"""Report roach-pi submodule health and scope-guard readiness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from adapters.roach_pi_guard import detect_mode, load_manifest, validate_scope_paths  # noqa: E402


def main() -> int:
    status = detect_mode(root=REPO)
    manifest = load_manifest(REPO)
    sample = validate_scope_paths(["02_RUNTIME/", "scripts/"], REPO)
    out = {
        "manifest": manifest,
        "runtime": status,
        "scope_guard_sample": sample,
        "init_hint": "powershell -File scripts/init_roach_pi_submodule.ps1",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
