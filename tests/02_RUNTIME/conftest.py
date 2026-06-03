"""Ensure 02_RUNTIME is on sys.path for all tests in this subtree."""

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[2] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))
