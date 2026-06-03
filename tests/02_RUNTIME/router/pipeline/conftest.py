"""conftest for router pipeline tests.

The tests/ directory structure mirrors 02_RUNTIME/router/pipeline/ and
contains __init__.py files, causing pytest to load empty stub packages for
'router' and 'router.pipeline' from the tests/ tree. This conftest:

1. Ensures 02_RUNTIME is on sys.path.
2. Extends the stub packages' __path__ to include the real source directories
   so that sub-modules (advisory.py, audit.py, billing.py, impact.py, io.py,
   policy.py, billing_axis.py, etc.) can be imported normally.
"""

from __future__ import annotations

import sys
from pathlib import Path

_WORKTREE = Path(__file__).resolve().parents[4]
_RUNTIME = _WORKTREE / "02_RUNTIME"
_ROUTER_SRC = _RUNTIME / "router"
_PIPELINE_SRC = _ROUTER_SRC / "pipeline"

# Ensure 02_RUNTIME is on sys.path (before everything else).
_rt_str = str(_RUNTIME)
if _rt_str not in sys.path:
    sys.path.insert(0, _rt_str)

# Fix the 'router' package __path__ so that sub-modules like router.policy,
# router.billing_axis, router.budget, etc. are findable.
_r = sys.modules.get("router")
if _r is not None:
    _r_path = getattr(_r, "__path__", [])
    if str(_ROUTER_SRC) not in _r_path:
        _r_path.append(str(_ROUTER_SRC))

# Fix the 'router.pipeline' package __path__ so that the real pipeline modules
# (advisory, audit, billing, impact, io) are importable.
_rp = sys.modules.get("router.pipeline")
if _rp is not None:
    _rp_path = getattr(_rp, "__path__", [])
    if str(_PIPELINE_SRC) not in _rp_path:
        _rp_path.append(str(_PIPELINE_SRC))
