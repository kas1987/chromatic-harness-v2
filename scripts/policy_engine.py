#!/usr/bin/env python3
"""Policy-as-code governance engine (bead gh-64).

A declarative rule engine that evaluates a small predicate language over a
context dict and renders an allow/block decision, with audit logging, policy
versioning, and a human-override workflow.

Five eval requirements:
  1. Declarative policy schema + validate_policy() (pure).
  2. Rule evaluation engine — evaluate() (pure).
  3. Audit logging — every CLI run appends to policy/audit.jsonl.
  4. Policy versioning — version field + load_policy() (active file or default).
  5. Override workflow — apply_override() flips a block to allow-with-override.

Usage:
    python scripts/policy_engine.py --context context.json
    cat context.json | python scripts/policy_engine.py --context -
    python scripts/policy_engine.py --context ctx.json \
        --override-reason "hotfix approved" --actor alice

Exit codes: 0 = allow (or allow-with-override), 1 = block.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "policy"
AUDIT_LOG = ARTIFACT_DIR / "audit.jsonl"
LATEST_ARTIFACT = ARTIFACT_DIR / "latest.json"
ACTIVE_POLICY_PATH = REPO / "00_SOURCE_OF_TRUTH" / "policies" / "active_policy.json"

VALID_SEVERITIES = ("info", "warn", "block")
VALID_OPS = ("==", "!=", ">", "<", ">=", "<=", "in", "contains")

# Eval 4: built-in fallback policy (used when no active policy file present).
DEFAULT_POLICY: dict = {
    "version": "0.1.0",
    "name": "default-governance-policy",
    "rules": [
        {
            "id": "large-change-set",
            "description": "Change set touches an unusually large number of files.",
            "severity": "warn",
            "when": {"field": "changed_files", "op": ">", "value": 50},
            "message": "Change set exceeds 50 files; request additional review.",
        },
        {
            "id": "protected-path-touched",
            "description": "A protected/governance path was modified.",
            "severity": "block",
            "when": {"field": "protected_touched", "op": "==", "value": True},
            "message": "Protected path touched; requires human override to proceed.",
        },
        {
            "id": "secrets-detected",
            "description": "Secret scanner flagged one or more findings.",
            "severity": "block",
            "when": {"field": "secrets_found", "op": ">", "value": 0},
            "message": "Potential secrets detected; resolve before proceeding.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Eval 1: declarative schema validation (pure)
# ---------------------------------------------------------------------------


def validate_policy(policy: dict) -> list[str]:
    """Validate a policy dict against the declarative schema.

    Returns a list of human-readable error strings (empty list => valid).
    Pure function: never raises, never performs I/O.
    """
    errors: list[str] = []

    if not isinstance(policy, dict):
        return ["policy must be a dict"]

    version = policy.get("version")
    if not isinstance(version, str) or not version.strip():
        errors.append("policy.version must be a non-empty string")

    rules = policy.get("rules")
    if not isinstance(rules, list):
        return errors + ["policy.rules must be a list"]

    seen_ids: set[str] = set()
    for idx, rule in enumerate(rules):
        prefix = f"rules[{idx}]"
        if not isinstance(rule, dict):
            errors.append(f"{prefix} must be a dict")
            continue

        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif rid in seen_ids:
            errors.append(f"{prefix}.id duplicate id '{rid}'")
        else:
            seen_ids.add(rid)

        if not isinstance(rule.get("description"), str):
            errors.append(f"{prefix}.description must be a string")

        sev = rule.get("severity")
        if sev not in VALID_SEVERITIES:
            errors.append(f"{prefix}.severity must be one of {VALID_SEVERITIES}, got {sev!r}")

        if not isinstance(rule.get("message"), str):
            errors.append(f"{prefix}.message must be a string")

        errors.extend(_validate_predicate(rule.get("when"), f"{prefix}.when"))

    return errors


def _validate_predicate(when: object, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(when, dict):
        return [f"{prefix} must be a dict"]
    if not isinstance(when.get("field"), str) or not when.get("field"):
        errors.append(f"{prefix}.field must be a non-empty string")
    op = when.get("op")
    if op not in VALID_OPS:
        errors.append(f"{prefix}.op must be one of {VALID_OPS}, got {op!r}")
    if "value" not in when:
        errors.append(f"{prefix}.value is required")
    return errors


# ---------------------------------------------------------------------------
# Eval 2: rule evaluation engine (pure)
# ---------------------------------------------------------------------------


def _apply_op(actual: object, op: str, expected: object) -> bool:
    """Apply a single declarative operator. Returns False on type mismatch."""
    try:
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == ">":
            return actual > expected  # type: ignore[operator]
        if op == "<":
            return actual < expected  # type: ignore[operator]
        if op == ">=":
            return actual >= expected  # type: ignore[operator]
        if op == "<=":
            return actual <= expected  # type: ignore[operator]
        if op == "in":
            # actual is a member of the expected collection
            return actual in expected  # type: ignore[operator]
        if op == "contains":
            # actual collection/string contains expected
            return expected in actual  # type: ignore[operator]
    except TypeError:
        return False
    return False


def evaluate(policy: dict, context: dict) -> dict:
    """Apply every rule's predicate to the context and render a decision.

    Returns:
        {
          "policy_version": str,
          "violations": [ {id, severity, message, field, op, value, actual}, ... ],
          "by_severity": {"info": n, "warn": n, "block": n},
          "decision": "allow" | "block",
        }

    Block iff any matched (violating) rule has severity "block".
    Pure function: no I/O.
    """
    violations: list[dict] = []
    by_severity = {sev: 0 for sev in VALID_SEVERITIES}

    for rule in policy.get("rules", []):
        when = rule.get("when", {})
        field = when.get("field")
        op = when.get("op")
        expected = when.get("value")
        actual = context.get(field)

        if _apply_op(actual, op, expected):
            sev = rule.get("severity", "info")
            if sev in by_severity:
                by_severity[sev] += 1
            violations.append(
                {
                    "id": rule.get("id"),
                    "severity": sev,
                    "message": rule.get("message", ""),
                    "field": field,
                    "op": op,
                    "value": expected,
                    "actual": actual,
                }
            )

    decision = "block" if by_severity.get("block", 0) > 0 else "allow"
    return {
        "policy_version": policy.get("version"),
        "violations": violations,
        "by_severity": by_severity,
        "decision": decision,
    }


# ---------------------------------------------------------------------------
# Eval 4: policy versioning / loading
# ---------------------------------------------------------------------------


def load_policy(path: Path | None = None) -> dict:
    """Load the active policy from disk, falling back to DEFAULT_POLICY.

    Reads ACTIVE_POLICY_PATH (or an explicit path). If missing, corrupt, or
    schema-invalid, returns a copy of DEFAULT_POLICY (fail-safe).
    """
    target = path if path is not None else ACTIVE_POLICY_PATH
    try:
        text = target.read_text(encoding="utf-8")
        policy = json.loads(text)
    except FileNotFoundError:
        return json.loads(json.dumps(DEFAULT_POLICY))
    except Exception:  # noqa: BLE001 — partially written / corrupt JSON
        return json.loads(json.dumps(DEFAULT_POLICY))

    if validate_policy(policy):
        # Invalid active policy -> fall back rather than evaluate garbage.
        return json.loads(json.dumps(DEFAULT_POLICY))
    return policy


# ---------------------------------------------------------------------------
# Eval 5: override workflow (pure-ish; mutates a copy of result)
# ---------------------------------------------------------------------------


def apply_override(result: dict, reason: str, actor: str) -> dict:
    """Record a human override that flips a block to allow-with-override.

    Returns a new result dict with an `override` block and (if it was a block)
    a flipped decision of "allow-with-override". Non-block decisions are
    returned unchanged except for recording the override metadata.
    """
    out = json.loads(json.dumps(result))
    override = {
        "applied": True,
        "reason": reason,
        "actor": actor,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "original_decision": result.get("decision"),
    }
    if result.get("decision") == "block":
        out["decision"] = "allow-with-override"
    out["override"] = override
    return out


# ---------------------------------------------------------------------------
# Eval 3: audit logging
# ---------------------------------------------------------------------------


def append_audit(result: dict, timestamp: str) -> Path:
    """Append a single audit line to policy/audit.jsonl."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    line = {
        "timestamp": timestamp,
        "policy_version": result.get("policy_version"),
        "decision": result.get("decision"),
        "violation_count": len(result.get("violations", [])),
        "override": bool(result.get("override", {}).get("applied")),
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    return AUDIT_LOG


def write_artifact(result: dict, timestamp: str) -> Path:
    """Persist policy/latest.json + a timestamped copy."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    LATEST_ARTIFACT.write_text(payload, encoding="utf-8")
    return LATEST_ARTIFACT


# ---------------------------------------------------------------------------
# summarize (fail-open)
# ---------------------------------------------------------------------------


def summarize() -> dict:
    """Compact summary for the closeout report. Never raises."""
    try:
        if not LATEST_ARTIFACT.exists():
            return {
                "status": "no_run",
                "decision": None,
                "violations": None,
                "policy_version": None,
            }
        data = json.loads(LATEST_ARTIFACT.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "decision": data.get("decision"),
            "violations": len(data.get("violations", [])),
            "policy_version": data.get("policy_version"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "error": str(exc),
            "decision": None,
            "violations": None,
            "policy_version": None,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_context(arg: str) -> dict:
    if arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(arg).read_text(encoding="utf-8")
    try:
        ctx = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"context is not valid JSON: {exc}") from exc
    if not isinstance(ctx, dict):
        raise ValueError("context must be a JSON object")
    return ctx


def main() -> int:
    ap = argparse.ArgumentParser(description="Policy-as-code governance engine (gh-64)")
    ap.add_argument("--context", required=True, help="JSON file path or '-' for stdin")
    ap.add_argument("--override-reason", default=None, help="Human override reason")
    ap.add_argument("--actor", default=None, help="Actor recording an override")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default=None, help="Override timestamp (ISO compact)")
    args = ap.parse_args()

    ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    context = _load_context(args.context)
    policy = load_policy()
    result = evaluate(policy, context)

    if args.override_reason:
        result = apply_override(result, args.override_reason, args.actor or "unknown")

    append_audit(result, ts)
    artifact = write_artifact(result, ts)

    decision = result["decision"]
    print("Policy engine evaluation:")
    print(f"  policy version: {result['policy_version']}")
    print(f"  decision:       {decision.upper()}")
    print(f"  violations:     {len(result['violations'])}")
    for v in result["violations"]:
        print(f"    [{v['severity']}] {v['id']}: {v['message']}")
    if result.get("override", {}).get("applied"):
        ov = result["override"]
        print(f"  override:       by {ov['actor']} -- {ov['reason']}")
    print(f"  artifact:       {artifact}")

    if args.json:
        print(json.dumps({**result, "timestamp": ts}, indent=2))

    return 1 if decision == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
