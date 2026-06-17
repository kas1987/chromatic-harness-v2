#!/usr/bin/env python3
"""Unified Chromatic Mission Packet validator (plan + dispatch).

Single canonical entry point for the whole mission lifecycle. Validates both:
  - PLAN packets (declare `level` M1-M4) — governance/planning rigor.
  - DISPATCH packets (declare `autonomy_level` L0-L5) — runtime contract.
A full-lifecycle packet may declare both.

Accepts YAML or JSON (by file extension), or a JSON object on stdin.

Enforces, in lockstep with 01_PROTOCOLS/CMP/mission_packet.schema.json:
  - BASE required fields (all packets).
  - PLAN profile: common plan fields + per-level required fields.
  - DISPATCH profile: agent_role + allowed_tools.
  - L5 autonomy gate: autonomy_level=L5 requires metadata.human_approved=true.
  - Mode autonomy ceilings (operator<=L4, auditor<=L2, designer<=L3).
  - confidence_score 0-100; risk_level enum.
If `jsonschema` is installed, the packet is additionally validated against the
schema for full structural rigor; otherwise the field checks above still apply.

Canonical field names: allowed_files/forbidden_files (not *_paths),
required_output (not required_outputs), confidence_score int (not
confidence_required float).

Usage:
  python scripts/validate_mission_packet.py <packet.yaml|.json>
  echo '{"mission_id": ...}' | python scripts/validate_mission_packet.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "01_PROTOCOLS" / "CMP" / "mission_packet.schema.json"

# Required for EVERY packet (mirrors schema top-level `required`).
BASE_REQUIRED = ["mission_id", "objective", "confidence_score", "stop_conditions", "required_output"]

# PLAN profile: required whenever `level` is present.
PLAN_COMMON = [
    "title",
    "scope",
    "success_criteria",
    "acceptance_criteria",
    "allowed_files",
    "forbidden_files",
    "tool_budget",
    "risk_level",
]
LEVEL_EXTRA = {
    "M1": ["plan", "validation"],
    "M2": [
        "background",
        "out_of_scope",
        "dependencies",
        "risks",
        "plan",
        "test_strategy",
        "rollback",
        "reviewers",
        "approval_required",
    ],
    "M3": [
        "background",
        "out_of_scope",
        "dependencies",
        "integration_points",
        "risks",
        "detailed_plan",
        "test_strategy",
        "rollback_plan",
        "impact_assessment",
        "reviewers",
        "approval_required",
    ],
    "M4": [
        "background",
        "out_of_scope",
        "dependencies",
        "stakeholder_map",
        "threat_model",
        "communication_plan",
        "risks",
        "full_impact_assessment",
        "comprehensive_plan",
        "test_strategy",
        "rollback_plan",
        "formal_approval",
    ],
}

# DISPATCH profile: required whenever `autonomy_level` is present.
DISPATCH_REQUIRED = ["agent_role", "allowed_tools"]

VALID_RISK = {"low", "medium", "high", "critical"}
L_RANK = {f"L{i}": i for i in range(6)}
MODE_CEILINGS = {"operator": "L4", "auditor": "L2", "designer": "L3"}


def _load(source: str | None) -> dict:
    if source is None:
        return json.loads(sys.stdin.read())
    path = Path(source)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    import yaml  # local import so JSON-only use needs no PyYAML

    return yaml.safe_load(text)


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["top-level document must be a mapping/object"]

    is_plan = "level" in data
    is_dispatch = "autonomy_level" in data
    if not is_plan and not is_dispatch:
        errors.append("packet declares neither `level` (plan) nor `autonomy_level` (dispatch)")

    required = list(BASE_REQUIRED)
    if is_plan:
        level = data.get("level")
        if level not in LEVEL_EXTRA:
            errors.append(f"invalid `level`: {level!r} (expected M1-M4)")
        else:
            required += PLAN_COMMON + LEVEL_EXTRA[level]
    if is_dispatch:
        required += DISPATCH_REQUIRED

    missing = [f for f in dict.fromkeys(required) if f not in data]
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    # L5 autonomy gate.
    level_a = data.get("autonomy_level")
    if level_a == "L5":
        if not data.get("metadata", {}).get("human_approved", False):
            errors.append(
                "autonomy_level=L5 requires metadata.human_approved=true "
                "(must be granted explicitly by a human operator)"
            )

    # Mode autonomy ceiling.
    mode = data.get("metadata", {}).get("mode")
    if mode and level_a in L_RANK:
        ceiling = MODE_CEILINGS.get(mode)
        if ceiling and L_RANK[level_a] > L_RANK[ceiling]:
            errors.append(f"mode '{mode}' ceiling is {ceiling}; packet sets autonomy_level={level_a} which exceeds it")

    # Scalar checks.
    conf = data.get("confidence_score")
    if conf is not None:
        try:
            if not (0 <= int(conf) <= 100):
                errors.append("confidence_score must be 0-100")
        except (TypeError, ValueError):
            errors.append("confidence_score must be an integer 0-100")
    risk = data.get("risk_level")
    if risk is not None and risk not in VALID_RISK:
        errors.append(f"risk_level must be one of {sorted(VALID_RISK)}")

    # Full schema validation when jsonschema is available.
    try:
        import jsonschema

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        v = jsonschema.Draft202012Validator(schema)
        for e in sorted(v.iter_errors(data), key=lambda e: list(e.path)):
            msg = f"schema: {e.message}"
            if msg not in errors:
                errors.append(msg)
    except ImportError:
        pass

    return errors


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        data = _load(source) or {}
    except Exception as exc:  # noqa: BLE001 - surface any load failure cleanly
        print(f"FAIL: could not load packet: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    label = source or "<stdin>"
    if errors:
        print(f"FAIL {label}:")
        for e in errors:
            print(f"  - {e}")
        return 1

    profiles = []
    if "level" in data:
        profiles.append(f"plan:{data['level']}")
    if "autonomy_level" in data:
        profiles.append(f"dispatch:{data['autonomy_level']}")
    print(f"PASS {label}: valid mission packet [{', '.join(profiles)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
