# Import Strategy: `src/` vs `02_RUNTIME/`

## Current State (2026-05-28)

Chromatic Harness v2 has two copies of the router package:

| Location | Status | Purpose |
|----------|--------|---------|
| `src/chromatic_router/` | **Incomplete scaffold** | Installable package (intended for PyPI / pip install) |
| `02_RUNTIME/router/` | **Canonical source** | Active runtime code used by tests, hooks, and adapters |

## Why Two Copies Exist

The `src/chromatic_router/` directory was created as a clean package scaffold with `__init__.py` and adapter stubs. However, active development continued in `02_RUNTIME/router/`, which now contains the full implementation:

- Core modules: `contracts.py`, `router.py`, `confidence.py`, `policy.py`, `privacy.py`, `budget.py`, `gate.py`
- Classifiers: `complexity_classifier.py`, `context_detector.py`, `provider_selector.py`
- Adapters: `kimi_adapter.py`, `mock.py`, `native_claude_adapter.py`, `ollama_adapter.py`, `ollama_remote.py`, `openhuman_adapter.py`, `prism_orchestrator_adapter.py`
- Utilities: `observability.py`

`src/chromatic_router/` only contains a subset of adapters (anthropic, featherless, google, lmstudio, openai, openrouter, ollama).

## Which Should You Import From?

### For Tests
Import from `router.*` (resolved via `02_RUNTIME/router/`). The test suite uses:

```python
from router.contracts import RouteRequest
from router.router import ChromaticRouter
```

This is configured automatically via `tests/conftest.py` and `pytest.ini` (`pythonpath = 02_RUNTIME`).

### For Hooks and Scripts
Import from `router.*` using `sys.path.insert` to add `02_RUNTIME`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "02_RUNTIME"))
from router.policy import PolicyLoader
```

### For Package Consumers (Future)
Once `src/chromatic_router/` is fully synced, install with:

```bash
pip install -e .
```

Then import:

```python
from chromatic_router import ChromaticRouter
from chromatic_router.contracts import RouteRequest
```

## Coverage

Test coverage is measured against `02_RUNTIME/router/` (the canonical source) via `.coveragerc`:

```bash
pytest tests/ --cov --cov-report=term
```

Current coverage: **62%**.

## Migration Path

To unify the two copies:

1. Copy all missing modules from `02_RUNTIME/router/` to `src/chromatic_router/`
2. Update `setup.py` / `pyproject.toml` to point to `src/`
3. Repoint tests to import from `chromatic_router.*`
4. Update `tests/conftest.py` and `pytest.ini`
5. Delete `02_RUNTIME/router/` after release cut

This is tracked as a future refactoring task, not part of the current sprint.
