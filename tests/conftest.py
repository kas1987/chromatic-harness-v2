"""pytest configuration for Chromatic Harness v2 tests."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_RUNTIME = _REPO / "02_RUNTIME"

# Ensure runtime modules are importable from test files
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_RUNTIME))
sys.path.insert(0, str(_RUNTIME / "api"))
