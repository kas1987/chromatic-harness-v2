"""Single validation path for the Chromatic discriminated event envelope.

All harness event types arrive as:
    {"kind": "<type>", "payload": {...}}

validate() checks the outer shape then dispatches payload validation to the
schema matching `kind`. Raises ValueError with a human-readable message on any
violation so callers don't need to import jsonschema directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_REPO_ROOT = Path(__file__).resolve().parents[2]

_KIND_TO_SCHEMA_PATH: dict[str, Path] = {
    "harness_event": _REPO_ROOT / "schemas" / "harness_event.schema.json",
    "magnet_event": _REPO_ROOT / "01_PROTOCOLS" / "MAGNETS" / "magnet_event.schema.json",
    "bead": _REPO_ROOT / "01_PROTOCOLS" / "BEADS" / "bead.schema.json",
}

VALID_KINDS = frozenset(_KIND_TO_SCHEMA_PATH)


def _load_schema(kind: str) -> dict:
    if kind not in _KIND_TO_SCHEMA_PATH:
        raise ValueError(f"Unknown kind {kind!r}; valid: {sorted(VALID_KINDS)}")
    path = _KIND_TO_SCHEMA_PATH[kind]
    return json.loads(path.read_text(encoding="utf-8"))


def validate_envelope(data: object) -> tuple[str, dict]:
    """Validate envelope shape; return (kind, payload).

    Does NOT validate the payload — call validate_payload() or validate() for that.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Envelope must be a JSON object, got {type(data).__name__}")
    kind = data.get("kind")
    if kind not in VALID_KINDS:
        raise ValueError(f"Unknown kind {kind!r}; must be one of {sorted(VALID_KINDS)}")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"'payload' must be a JSON object, got {type(payload).__name__}")
    extra = set(data) - {"kind", "payload"}
    if extra:
        raise ValueError(f"Unexpected envelope fields: {sorted(extra)}")
    return kind, payload


def validate_payload(kind: str, payload: dict) -> None:
    """Validate payload against the JSON Schema for the given kind.

    Raises ValueError on the first schema violation or unknown kind.
    Raises RuntimeError if the jsonschema package is not installed.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RuntimeError("jsonschema is required for envelope validation: pip install jsonschema") from exc

    schema = _load_schema(kind)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.absolute_path) or "<root>"
        raise ValueError(f"Payload schema violation for kind={kind!r} at {path}: {first.message}")


def validate(data: object) -> tuple[str, dict]:
    """Full envelope + payload validation. Returns (kind, payload).

    The canonical single entry-point: call this at every ingest boundary.
    """
    kind, payload = validate_envelope(data)
    validate_payload(kind, payload)
    return kind, payload
