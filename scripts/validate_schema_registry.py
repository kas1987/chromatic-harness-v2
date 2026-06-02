#!/usr/bin/env python3
"""CI validator for 01_PROTOCOLS/_schema_registry.yaml.

Checks:
  1. Every schema_path listed in the registry exists and is valid JSON.
  2. For schemas with jsonl_paths, validates up to SAMPLE_LINES lines from
     each JSONL file against the schema using jsonschema.
  3. Empty/absent JSONL files are skipped (not a failure).

Exit 0 = all checks passed. Exit 1 = at least one failure.

Usage:
    python scripts/validate_schema_registry.py [--registry PATH] [--sample N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install PyYAML")
    sys.exit(1)

try:
    import jsonschema
    from jsonschema import Draft202012Validator, FormatChecker, ValidationError
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "01_PROTOCOLS" / "_schema_registry.yaml"
DEFAULT_SAMPLE = 50


def load_registry(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("schemas", [])


def load_json_schema(schema_path: Path) -> dict[str, Any]:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_jsonl(jsonl_path: Path, schema: dict, sample: int) -> list[str]:
    """Return list of error strings (empty = pass)."""
    errors: list[str] = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    line_num = 0
    validated = 0

    with open(jsonl_path, encoding="utf-8") as fh:
        for raw in fh:
            line_num += 1
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"  line {line_num}: JSON parse error — {exc}")
                continue
            try:
                validator.validate(record)
            except ValidationError as exc:
                errors.append(f"  line {line_num}: {exc.message} (path: {list(exc.path)})")
            validated += 1
            if validated >= sample:
                break

    return errors


def run(registry_path: Path, sample: int) -> int:
    entries = load_registry(registry_path)
    if not entries:
        print(f"WARN  No schemas found in {registry_path}")
        return 0

    failures = 0
    total_schemas = 0
    total_jsonl_checked = 0

    for entry in entries:
        schema_id = entry.get("id", "?")
        rel_schema = entry.get("schema_path", "")
        schema_abs = REPO_ROOT / rel_schema
        total_schemas += 1

        # 1. Schema file must exist and be valid JSON
        if not schema_abs.is_file():
            print(f"FAIL  [{schema_id}] schema file missing: {rel_schema}")
            failures += 1
            continue

        try:
            schema = load_json_schema(schema_abs)
        except json.JSONDecodeError as exc:
            print(f"FAIL  [{schema_id}] schema is invalid JSON: {exc}")
            failures += 1
            continue

        # Basic meta-schema check
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            print(f"FAIL  [{schema_id}] schema fails meta-validation: {exc}")
            failures += 1
            continue

        schema_ok = True

        # 2. Validate any listed JSONL files
        for rel_jsonl in entry.get("jsonl_paths") or []:
            jsonl_abs = REPO_ROOT / rel_jsonl
            if not jsonl_abs.is_file():
                # Not a failure: runtime files are gitignored on clean checkouts
                print(f"SKIP  [{schema_id}] JSONL absent (OK): {rel_jsonl}")
                continue

            stat = jsonl_abs.stat()
            if stat.st_size == 0:
                print(f"SKIP  [{schema_id}] JSONL empty (OK): {rel_jsonl}")
                continue

            total_jsonl_checked += 1
            errs = validate_jsonl(jsonl_abs, schema, sample)
            if errs:
                print(f"FAIL  [{schema_id}] {rel_jsonl} — {len(errs)} violation(s):")
                for e in errs[:10]:
                    print(e)
                if len(errs) > 10:
                    print(f"  … {len(errs) - 10} more")
                failures += 1
                schema_ok = False
            else:
                print(f"PASS  [{schema_id}] {rel_jsonl}")

        if schema_ok and not any(
            (REPO_ROOT / p).is_file() and (REPO_ROOT / p).stat().st_size > 0 for p in (entry.get("jsonl_paths") or [])
        ):
            print(f"PASS  [{schema_id}] schema valid (no live JSONL to check)")

    print()
    print(f"Schemas checked : {total_schemas}")
    print(f"JSONL files validated : {total_jsonl_checked}")
    if failures == 0:
        print("All checks PASSED.")
        return 0
    print(f"{failures} check(s) FAILED.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to _schema_registry.yaml",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=DEFAULT_SAMPLE,
        help="Max JSONL lines to validate per file (default: 50)",
    )
    args = parser.parse_args()
    sys.exit(run(Path(args.registry), args.sample))


if __name__ == "__main__":
    main()
