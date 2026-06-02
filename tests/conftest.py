"""pytest configuration for Chromatic Harness v2 tests."""

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_RUNTIME = _REPO / "02_RUNTIME"
_SRC = _REPO / "src"

# Ensure runtime modules are importable from test files
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_RUNTIME))
sys.path.insert(0, str(_RUNTIME / "api"))


@pytest.fixture(autouse=True)
def _clean_gate_test_modules():
    """Remove stale gate-test module aliases after each test.

    When test_gate_context_tokens.py previously used
    spec_from_file_location("gate_test", ...) it injected a parallel copy of
    router.gate (and its transitive imports including router.contracts) under a
    shadow key.  That shadow copy shares no identity with the canonical
    sys.modules["router.contracts"], so isinstance(ctx, RoutingContext) returns
    False in unrelated tests that imported the real module.

    This fixture ensures any such aliases are evicted between tests so every
    test sees a single, consistent module identity.
    """
    yield
    for key in list(sys.modules.keys()):
        if key in ("gate_test",) or (key.startswith("router.") and "gate_test" in key):
            del sys.modules[key]
