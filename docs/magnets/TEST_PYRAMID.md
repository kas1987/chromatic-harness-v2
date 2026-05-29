# Test Pyramid Validation (Confidence Magnet)

The Confidence Magnet classifies each test as **unit**, **integration**, or **e2e** and compares counts to the default target ratio **70 / 20 / 10**.

## Classification

| Layer | Heuristics |
|-------|------------|
| e2e | Name/path: `e2e`, `playwright`, `cypress`, `/e2e/` |
| integration | `integration`, `api_test`, `/integration/` |
| unit | Everything else |

Explicit override: `TestResult.layer` or signal `layer` in Python.

## Warnings

- **Drift** (Δ ≥ 15%): info-level anomaly
- **Imbalance** (Δ ≥ 25%): warn-level anomaly + confidence penalty
- **Inverted** (more e2e than unit, ≥3 tests): additional warning

## Code

- TypeScript: `02_RUNTIME/magnets/test_pyramid.ts`, wired in `confidence-magnet.ts`
- Python: `02_RUNTIME/magnets/test_pyramid.py`, wired in `confidence_magnet.py`

```bash
python -m pytest tests/test_test_pyramid.py -q
```
