#!/usr/bin/env python3
"""Validate a Chromatic Mission Packet JSON against the CMP schema.

Enforces:
  - JSON Schema compliance (via jsonschema if available; falls back to required-field check)
  - L5 autonomy gate: autonomy_level="L5" requires metadata.human_approved=true

Usage:
  python scripts/validate_mission_packet.py <packet.json>
  echo '{"mission_id": ..., ...}' | python scripts/validate_mission_packet.py

Exit 0 on pass; non-zero on validation failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "01_PROTOCOLS" / "CMP" / "mission_packet.schema.json"

REQUIRED_FIELDS = [
    "mission_id",
    "objective",
    "agent_role",
    "autonomy_level",
    "confidence_required",
    "allowed_tools",
    "stop_conditions",
    "required_outputs",
]


def _load_packet(source: str | None) -> dict:
    if source:
        return json.loads(Path(source).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def validate(packet: dict) -> list[str]:
    errors: list[str] = []

    missing = [f for f in REQUIRED_FIELDS if f not in packet]
    if missing:
        errors.append(f"Missing required fields: {missing}")

    level = packet.get("autonomy_level", "")
    if level == "L5":
        approved = packet.get("metadata", {}).get("human_approved", False)
        if not approved:
            errors.append(
                "autonomy_level=L5 requires metadata.human_approved=true; "
                "L5 (Trusted Agent) must be granted explicitly by a human operator."
            )

    mode = packet.get("metadata", {}).get("mode")
    if mode and level:
        ceilings = {"operator": "L4", "auditor": "L2", "designer": "L3"}
        ceiling = ceilings.get(mode)
        if ceiling and level > ceiling:
            errors.append(
                f"Mode '{mode}' has autonomy ceiling {ceiling}; packet sets autonomy_level={level} which exceeds it."
            )

    try:
        import jsonschema  # type: ignore

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(packet, schema)
    except ImportError:
        pass
    except jsonschema.ValidationError as exc:
        errors.append(f"Schema violation: {exc.message}")

    return errors


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        packet = _load_packet(source)
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Failed to load packet: {exc}") from exc

    errors = validate(packet)
    if errors:
        raise SystemExit("Mission packet validation failed:\n  " + "\n  ".join(errors))

    print(f"Mission packet valid: {packet.get('mission_id', '?')} (autonomy={packet.get('autonomy_level')})")


if __name__ == "__main__":
    main()
