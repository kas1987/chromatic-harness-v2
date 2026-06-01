#!/usr/bin/env python3
"""memory_gate.py — Memory write gate with confidence scoring (GH #86).

Prevents long-term memory drift through controlled, evidence-backed writes.
Every write requires:
  - An evidence source (where the knowledge comes from)
  - A rationale (why it should be written)
  - A confidence score (0.0–1.0)
  - An author identifier

Gate function:
    gate_memory_write(key, value, evidence, confidence, author)

Contradiction detection: new writes are checked against existing keys for
semantic conflicts. Conflicting writes with high confidence are flagged and
quarantined pending review.

Provenance: every write appends a JSON record to
    07_LOGS_AND_AUDIT/memory_gate/provenance.jsonl

Storage: gated memories are written to
    .agents/memory/gated_store.json  (key → record)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
GATE_AUDIT_DIR = REPO / "07_LOGS_AND_AUDIT" / "memory_gate"
PROVENANCE_LOG = GATE_AUDIT_DIR / "provenance.jsonl"
GATED_STORE = REPO / ".agents" / "memory" / "gated_store.json"
QUARANTINE_STORE = REPO / ".agents" / "memory" / "quarantine.json"

# Minimum confidence to write (below this, the write is quarantined).
MIN_CONFIDENCE_TO_WRITE = 0.50
# At or above this threshold, a contradiction triggers quarantine of new write.
CONTRADICTION_CONFLICT_THRESHOLD = 0.75


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_store(path: Path) -> dict[str, Any]:
    """Load a JSON store, returning empty dict on missing/malformed file."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_provenance(record: dict) -> None:
    GATE_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with PROVENANCE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# ── Validation ───────────────────────────────────────────────────────────────


class MemoryWriteError(ValueError):
    """Raised when a memory write is rejected by the gate."""


def validate_inputs(
    key: str,
    value: Any,
    evidence: str,
    confidence: float,
    author: str,
) -> list[str]:
    """Return a list of validation error messages (empty = valid)."""
    errors: list[str] = []

    if not key or not str(key).strip():
        errors.append("key must be a non-empty string")
    if value is None:
        errors.append("value must not be None")
    if not evidence or not str(evidence).strip():
        errors.append("evidence (source/rationale) must be provided")
    if not isinstance(confidence, (int, float)):
        errors.append(f"confidence must be a float 0.0–1.0, got {confidence!r}")
    elif not (0.0 <= float(confidence) <= 1.0):
        errors.append(f"confidence {confidence} out of range 0.0–1.0")
    if not author or not str(author).strip():
        errors.append("author must be provided")

    return errors


# ── Contradiction detection ──────────────────────────────────────────────────


def _simple_contradiction_score(existing_value: Any, new_value: Any) -> float:
    """
    Heuristic contradiction score between two values.

    Returns 0.0 (no conflict) to 1.0 (direct contradiction).
    Uses string similarity heuristics when values are strings.
    """
    if existing_value == new_value:
        return 0.0  # Identical — no conflict.

    # If types differ meaningfully, mild conflict.
    if type(existing_value) is not type(new_value):
        return 0.3

    # For booleans, exact opposition.
    if isinstance(existing_value, bool) and isinstance(new_value, bool):
        return 1.0 if existing_value != new_value else 0.0

    # For strings, check for negation signals.
    if isinstance(existing_value, str) and isinstance(new_value, str):
        neg_words = {"not", "never", "no", "false", "disabled", "off", "reject", "deny"}
        old_has_neg = any(w in existing_value.lower().split() for w in neg_words)
        new_has_neg = any(w in new_value.lower().split() for w in neg_words)
        if old_has_neg != new_has_neg:
            return 0.7  # One negates, other affirms — likely conflict.
        if existing_value.lower() != new_value.lower():
            return 0.2  # Different strings, no negation — minor drift.

    # For numerics, relative distance.
    try:
        ev = float(existing_value)
        nv = float(new_value)
        if ev == 0 and nv == 0:
            return 0.0
        diff = abs(ev - nv) / max(abs(ev), abs(nv), 1.0)
        return min(diff, 1.0)
    except (TypeError, ValueError):
        pass

    return 0.15  # Default: minor drift, different values.


def detect_contradiction(
    key: str,
    new_value: Any,
    new_confidence: float,
    store: dict,
) -> dict | None:
    """
    Check if new_value contradicts an existing memory entry for key.

    Returns a conflict record if contradiction detected at high confidence,
    otherwise None.
    """
    if key not in store:
        return None

    existing = store[key]
    existing_value = existing.get("value")
    existing_confidence = float(existing.get("confidence", 0.5))

    conflict_score = _simple_contradiction_score(existing_value, new_value)

    # Only flag if both new and existing have high confidence AND conflict is notable.
    if conflict_score >= 0.5 and new_confidence >= CONTRADICTION_CONFLICT_THRESHOLD:
        return {
            "key": key,
            "conflict_score": round(conflict_score, 3),
            "existing_value": existing_value,
            "existing_confidence": existing_confidence,
            "new_value": new_value,
            "new_confidence": new_confidence,
            "existing_author": existing.get("author"),
            "existing_timestamp": existing.get("timestamp"),
        }
    return None


# ── Gate function ────────────────────────────────────────────────────────────


def gate_memory_write(
    key: str,
    value: Any,
    evidence: str,
    confidence: float,
    author: str,
    dry_run: bool = False,
) -> dict:
    """
    Gated memory write with validation, contradiction check, and provenance.

    Parameters:
        key:        Memory key (e.g. "governance.policy_version")
        value:      Value to store (any JSON-serializable type)
        evidence:   Source and rationale string
        confidence: Float 0.0–1.0 (0.0 = pure guess, 1.0 = verified fact)
        author:     Identifier of the writing agent or human
        dry_run:    If True, validate and check but do not write

    Returns:
        {
            "status": "written" | "quarantined" | "rejected" | "dry_run",
            "key": ...,
            "confidence": ...,
            "contradiction": None | {...},
            "timestamp": ...,
            "provenance": {...}
        }
    """
    errors = validate_inputs(key, value, evidence, confidence, author)
    if errors:
        raise MemoryWriteError(f"Validation failed: {'; '.join(errors)}")

    confidence = float(confidence)
    ts = _ts()

    provenance = {
        "key": key,
        "author": author,
        "evidence": evidence,
        "confidence": confidence,
        "timestamp": ts,
        "dry_run": dry_run,
    }

    store = _load_store(GATED_STORE)
    contradiction = detect_contradiction(key, value, confidence, store)

    result: dict[str, Any] = {
        "status": "pending",
        "key": key,
        "confidence": confidence,
        "contradiction": contradiction,
        "timestamp": ts,
        "provenance": provenance,
    }

    # Low confidence: quarantine.
    if confidence < MIN_CONFIDENCE_TO_WRITE:
        result["status"] = "quarantined"
        result["reason"] = f"Confidence {confidence} < minimum {MIN_CONFIDENCE_TO_WRITE}. Quarantined pending review."
        if not dry_run:
            q_store = _load_store(QUARANTINE_STORE)
            q_store[f"{key}::{ts}"] = {
                "key": key,
                "value": value,
                "provenance": provenance,
                "quarantine_reason": result["reason"],
            }
            _save_store(QUARANTINE_STORE, q_store)
            provenance["status"] = "quarantined"
            _append_provenance(provenance)
        return result

    # Contradiction at high confidence: quarantine the new write.
    if contradiction and contradiction["conflict_score"] >= 0.7:
        result["status"] = "quarantined"
        result["reason"] = (
            f"Contradiction detected (conflict_score={contradiction['conflict_score']}) with existing "
            f"entry (confidence={contradiction['existing_confidence']}). Quarantined pending review."
        )
        if not dry_run:
            q_store = _load_store(QUARANTINE_STORE)
            q_store[f"{key}::{ts}"] = {
                "key": key,
                "value": value,
                "provenance": provenance,
                "quarantine_reason": result["reason"],
                "contradiction": contradiction,
            }
            _save_store(QUARANTINE_STORE, q_store)
            provenance["status"] = "quarantined"
            _append_provenance(provenance)
        return result

    # All checks pass: write.
    if dry_run:
        result["status"] = "dry_run"
        result["would_write"] = True
        return result

    record = {
        "value": value,
        "provenance": provenance,
        "confidence": confidence,
        "author": author,
        "timestamp": ts,
        "evidence": evidence,
        "contradiction_at_write": contradiction,
    }
    store[key] = record
    _save_store(GATED_STORE, store)

    provenance["status"] = "written"
    _append_provenance(provenance)

    result["status"] = "written"
    return result


# ── Read helper ──────────────────────────────────────────────────────────────


def read_memory(key: str) -> dict | None:
    """Return the stored record for key, or None if absent."""
    store = _load_store(GATED_STORE)
    return store.get(key)


def list_memories(prefix: str = "") -> list[dict]:
    """Return all memory entries, optionally filtered by key prefix."""
    store = _load_store(GATED_STORE)
    result = []
    for k, v in store.items():
        if prefix and not k.startswith(prefix):
            continue
        result.append({"key": k, **v})
    return sorted(result, key=lambda x: x.get("timestamp", ""))


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Memory write gate with confidence scoring (GH #86)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Write a memory entry
  python 02_RUNTIME/memory/memory_gate.py write \\
    --key "governance.policy_version" \\
    --value "2026-06" \\
    --evidence "Observed in auto-mode-scope.yaml line 5" \\
    --confidence 0.95 \\
    --author "verifier-agent"

  # Dry-run a write
  python 02_RUNTIME/memory/memory_gate.py write --key foo --value bar \\
    --evidence "test" --confidence 0.8 --author ci --dry-run

  # Read a key
  python 02_RUNTIME/memory/memory_gate.py read --key "governance.policy_version"

  # List all memories
  python 02_RUNTIME/memory/memory_gate.py list
""",
    )
    sub = ap.add_subparsers(dest="command")

    wp = sub.add_parser("write", help="Write a memory entry through the gate")
    wp.add_argument("--key", required=True)
    wp.add_argument("--value", required=True, help="Value (interpreted as JSON if valid, else string)")
    wp.add_argument("--evidence", required=True)
    wp.add_argument("--confidence", required=True, type=float)
    wp.add_argument("--author", required=True)
    wp.add_argument("--dry-run", action="store_true")

    rp = sub.add_parser("read", help="Read a memory entry by key")
    rp.add_argument("--key", required=True)

    lp = sub.add_parser("list", help="List all memory entries")
    lp.add_argument("--prefix", default="", help="Filter by key prefix")

    args = ap.parse_args()

    if not args.command:
        ap.print_help()
        return 1

    if args.command == "read":
        record = read_memory(args.key)
        if record is None:
            print(json.dumps({"error": f"Key '{args.key}' not found"}))
            return 1
        print(json.dumps(record, indent=2))
        return 0

    if args.command == "list":
        entries = list_memories(args.prefix)
        print(json.dumps(entries, indent=2))
        return 0

    # write
    try:
        value: Any = args.value
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            pass  # treat as raw string

        result = gate_memory_write(
            key=args.key,
            value=value,
            evidence=args.evidence,
            confidence=args.confidence,
            author=args.author,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2))
        status = result.get("status", "unknown")
        if status in {"written", "dry_run"}:
            return 0
        return 1  # quarantined or rejected
    except MemoryWriteError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
