#!/usr/bin/env python3
"""mutation_manifest.py — pre-write declaration gate (P0-CC-002 / ju0o.2).

Every write-capable autonomous task must produce a mutation manifest before it
mutates state: what it intends to change, risk tier, allowed/forbidden files,
acceptance checks, rollback plan, and whether a verifier is required.

This module is the schema validator + the enforcement helper GO-mode calls to
reject writes that lack a valid manifest (FR-3 of PDR_COLLISION_CONTROL).

Network-free, dependency-free (hand-rolled JSON-Schema subset — no jsonschema).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "schemas" / "mutation_manifest.schema.json"

WRITE_MODES = {"write", "exclusive"}


def load_schema(path: Path | None = None) -> dict:
    return json.loads((path or SCHEMA_PATH).read_text(encoding="utf-8"))


def validate_manifest(manifest: dict, schema: dict | None = None) -> list[str]:
    """Return a list of validation errors ([] means valid). Hand-rolled subset:
    required fields, enum, and primitive types — enough for the manifest contract."""
    schema = schema or load_schema()
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]

    for field in schema.get("required", []):
        if field not in manifest:
            errors.append(f"missing required field: {field}")

    props = schema.get("properties", {})
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    for key, spec in props.items():
        if key not in manifest:
            continue
        val = manifest[key]
        if "enum" in spec and val not in spec["enum"]:
            errors.append(f"{key}={val!r} not in {spec['enum']}")
        declared = spec.get("type")
        if declared:
            types = declared if isinstance(declared, list) else [declared]
            py = tuple(
                t
                for name in types
                for t in ((type_map[name],) if not isinstance(type_map[name], tuple) else type_map[name])
            )
            # bool is a subclass of int — guard so a bool isn't accepted as integer/number
            if not isinstance(val, py) or (bool not in py and isinstance(val, bool)):
                errors.append(f"{key} has wrong type (expected {declared})")
        if "minimum" in spec and isinstance(val, (int, float)) and not isinstance(val, bool) and val < spec["minimum"]:
            errors.append(f"{key}={val} below minimum {spec['minimum']}")
        if "maximum" in spec and isinstance(val, (int, float)) and not isinstance(val, bool) and val > spec["maximum"]:
            errors.append(f"{key}={val} above maximum {spec['maximum']}")
    return errors


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid(manifest: dict, schema: dict | None = None) -> bool:
    return not validate_manifest(manifest, schema)


def require_manifest(task: dict, manifest: dict | None = None, schema: dict | None = None) -> tuple[bool, str]:
    """Enforcement gate for GO-mode (FR-3).

    A task that does NOT write (mode read/verify, or no write intent) needs no
    manifest. A write-capable task is rejected unless it carries a valid manifest.
    Returns (allowed, reason).
    """
    mode = str(task.get("mode", "")).lower()
    writes = mode in WRITE_MODES or bool(task.get("requires_manifest"))
    if not writes:
        return True, "no write intent; manifest not required"
    if manifest is None:
        manifest = task.get("mutation_manifest")
    if manifest is None:
        return False, "write task rejected: no mutation manifest attached"
    errors = validate_manifest(manifest, schema)
    if errors:
        return False, f"write task rejected: invalid manifest ({'; '.join(errors[:3])})"
    return True, "valid mutation manifest"


def main() -> int:
    ap = argparse.ArgumentParser(description="Mutation manifest validator / gate (P0-CC-002)")
    ap.add_argument("--validate", metavar="MANIFEST_JSON", help="validate a manifest file against the schema")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.validate:
        manifest = load_manifest(Path(args.validate))
        errors = validate_manifest(manifest)
        result = {"valid": not errors, "errors": errors}
        print(
            json.dumps(result, indent=2)
            if args.json
            else ("VALID" if not errors else "INVALID:\n  " + "\n  ".join(errors))
        )
        return 0 if not errors else 1

    print("usage: mutation_manifest.py --validate <manifest.json>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
