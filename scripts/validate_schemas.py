#!/usr/bin/env python3
"""Standalone schema validator for core Chromatic Harness v2 Pydantic models.

Usage:
    python scripts/validate_schemas.py

Exits 0 if all model validations pass, 1 if any fail.
"""

import sys
import os

# Ensure the api package is importable from the repo root
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUNTIME = os.path.join(_REPO, "02_RUNTIME")
_API = os.path.join(_RUNTIME, "api")

for _p in (_REPO, _RUNTIME, _API):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pydantic import ValidationError  # noqa: E402

try:
    from api.models import (  # noqa: E402
        CreateMissionRequest,
        CreateEventRequest,
        CreateBeadRequest,
    )
except ImportError:
    # Fallback: import directly from the models module path
    import importlib.util as ilu

    _spec = ilu.spec_from_file_location("models", os.path.join(_API, "models.py"))
    _mod = ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    CreateMissionRequest = _mod.CreateMissionRequest
    CreateEventRequest = _mod.CreateEventRequest
    CreateBeadRequest = _mod.CreateBeadRequest


# ---------------------------------------------------------------------------
# Known-good payloads for each core model
# ---------------------------------------------------------------------------

KNOWN_GOOD = {
    "CreateMissionRequest": (
        CreateMissionRequest,
        {
            "objective": "Validate schema harness end-to-end",
            "agent_role": "agent_lead",
            "autonomy_level": "L2",
            "confidence_required": 80.0,
            "allowed_tools": ["bash", "read"],
            "stop_conditions": ["drift > 20"],
            "required_outputs": ["report", "bead"],
        },
    ),
    "CreateEventRequest": (
        CreateEventRequest,
        {
            "magnet_name": "intent_magnet",
            "inflection_point": "task_start",
            "observed_signal": {"clarity": 0.95, "scope": "well-defined"},
            "risk_delta": -0.5,
            "confidence_delta": 2.0,
            "evidence": ["step 1 logged", "checkpoint passed"],
            "recommended_action": "continue",
        },
    ),
    "CreateBeadRequest": (
        CreateBeadRequest,
        {
            "title": "Schema Validation Bead",
            "objective": "Prove that all Pydantic models validate correctly",
            "priority": "p1",
            "source": "magnet",
            "mission_id": None,
        },
    ),
}


def run() -> int:
    """Validate each model with its known-good payload. Returns exit code."""
    failures = 0

    for model_name, (model_cls, payload) in KNOWN_GOOD.items():
        try:
            instance = model_cls(**payload)
            # Quick sanity: round-trip through model_dump
            dumped = instance.model_dump()
            assert isinstance(dumped, dict), "model_dump() did not return a dict"
            print(f"PASS  {model_name}")
        except ValidationError as exc:
            print(f"FAIL  {model_name}")
            print(f"      ValidationError: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {model_name}")
            print(f"      Unexpected error: {type(exc).__name__}: {exc}")
            failures += 1

    print()
    if failures == 0:
        print(f"All {len(KNOWN_GOOD)} model validations PASSED.")
        return 0
    else:
        print(f"{failures}/{len(KNOWN_GOOD)} model validations FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run())
