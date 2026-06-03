"""Ensure 02_RUNTIME is on sys.path for all tests in this subtree."""

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[2] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# Eagerly import workflows so module-level sys.modules stubs in test files
# (e.g. test_session_lock.py) cannot shadow the real package via setdefault.
try:
    import workflows  # noqa: F401
    import workflows.run_log  # noqa: F401
except ImportError:
    pass
