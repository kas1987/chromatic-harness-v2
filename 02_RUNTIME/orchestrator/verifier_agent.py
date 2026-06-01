#!/usr/bin/env python3
"""verifier_agent.py — Independent verifier agent for T3+ mutations (GH #82).

Reads a pending mutation JSON, runs structural checks, and outputs a verdict
(approve / reject / escalate). T3+ mutations require review evidence before
promotion. The audit trail is written to 07_LOGS_AND_AUDIT/verifier/.

Usage:
    python 02_RUNTIME/orchestrator/verifier_agent.py --mutation-file <path> [--dry-run]
    python 02_RUNTIME/orchestrator/verifier_agent.py --help

Mutation file schema (JSON):
    {
        "id": "str",
        "title": "str",
        "tier": "T1" | "T2" | "T3" | "T4",          # required for T3+ gate
        "confidence_score": float,                     # 0–100
        "allowed_files": ["path", ...],               # declared scope
        "changed_files": ["path", ...],               # actual changes
        "forbidden_patterns": ["pattern", ...],        # optional
        "test_evidence": "str | null",                 # test run summary
        "risk_level": "low" | "medium" | "high" | "critical",
        "author": "str",
        "timestamp": "ISO8601"
    }

Output:
    {
        "verdict": "approve" | "reject" | "escalate",
        "evidence": [{"check": str, "status": "pass"|"fail"|"warn", "detail": str}],
        "tier": "T3",
        "confidence_score": 82.5,
        "timestamp": "2026-06-01T00:00:00Z",
        "remediation_task": null | {"action": str, "reason": str}
    }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
AUDIT_DIR = REPO / "07_LOGS_AND_AUDIT" / "verifier"

# Tiers that require independent verification.
VERIFICATION_REQUIRED_TIERS = {"T3", "T4"}

# Confidence thresholds by tier.
CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "T1": 40.0,
    "T2": 60.0,
    "T3": 75.0,
    "T4": 90.0,
}

# Patterns that are never allowed in mutated content/paths.
DEFAULT_FORBIDDEN_PATTERNS = [
    r"\.env$",
    r"\.pem$",
    r"\.key$",
    r"settings\.json$",
    r"secrets",
    r"credentials",
]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_mutation(path: str) -> dict[str, Any]:
    """Load and validate mutation file. Raises on parse failure."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Mutation file is not valid JSON: {exc}") from exc
    except FileNotFoundError:
        raise ValueError(f"Mutation file not found: {path}")


# ── Individual checks ────────────────────────────────────────────────────────


def check_tier_gate(mutation: dict) -> dict:
    """Verify that the mutation tier warrants verification and is declared."""
    tier = str(mutation.get("tier", "")).upper()
    if not tier:
        return {"check": "tier_gate", "status": "fail", "detail": "No tier declared in mutation file."}
    if tier not in {"T1", "T2", "T3", "T4"}:
        return {"check": "tier_gate", "status": "fail", "detail": f"Unknown tier '{tier}'. Must be T1–T4."}
    if tier in VERIFICATION_REQUIRED_TIERS:
        return {
            "check": "tier_gate",
            "status": "pass",
            "detail": f"Tier {tier} correctly requires independent verification.",
        }
    return {
        "check": "tier_gate",
        "status": "warn",
        "detail": f"Tier {tier} does not normally require verification; verifier invoked explicitly.",
    }


def check_file_scope(mutation: dict) -> dict:
    """Verify changed_files are within allowed_files scope."""
    allowed: list[str] = mutation.get("allowed_files") or []
    changed: list[str] = mutation.get("changed_files") or []

    if not changed:
        return {"check": "file_scope", "status": "warn", "detail": "No changed_files declared; cannot verify scope."}
    if not allowed:
        return {"check": "file_scope", "status": "warn", "detail": "No allowed_files declared; scope unverifiable."}

    # Normalize to forward-slash paths for comparison.
    def norm(p: str) -> str:
        return p.replace("\\", "/").lower()

    out_of_scope = []
    for cf in changed:
        cf_norm = norm(cf)
        in_scope = any(cf_norm.startswith(norm(a)) or norm(a) in cf_norm for a in allowed)
        if not in_scope:
            out_of_scope.append(cf)

    if out_of_scope:
        return {
            "check": "file_scope",
            "status": "fail",
            "detail": f"{len(out_of_scope)} file(s) outside declared scope: {out_of_scope[:5]}",
        }
    return {
        "check": "file_scope",
        "status": "pass",
        "detail": f"All {len(changed)} changed file(s) within declared allowed_files scope.",
    }


def check_forbidden_patterns(mutation: dict) -> dict:
    """Ensure no forbidden file patterns appear in changed_files."""
    changed: list[str] = mutation.get("changed_files") or []
    extra_patterns: list[str] = mutation.get("forbidden_patterns") or []
    all_patterns = DEFAULT_FORBIDDEN_PATTERNS + extra_patterns

    violations = []
    for cf in changed:
        for pat in all_patterns:
            try:
                if re.search(pat, cf, re.IGNORECASE):
                    violations.append(f"{cf!r} matches forbidden pattern {pat!r}")
            except re.error:
                pass  # skip malformed patterns

    if violations:
        return {
            "check": "forbidden_patterns",
            "status": "fail",
            "detail": f"Forbidden pattern match(es): {violations[:3]}",
        }
    return {
        "check": "forbidden_patterns",
        "status": "pass",
        "detail": "No forbidden file patterns detected in changed_files.",
    }


def check_test_coverage(mutation: dict) -> dict:
    """Verify test evidence is present."""
    evidence = mutation.get("test_evidence")
    tier = str(mutation.get("tier", "")).upper()
    risk = str(mutation.get("risk_level", "medium")).lower()

    if not evidence or str(evidence).strip() in {"", "null", "none"}:
        if tier in VERIFICATION_REQUIRED_TIERS or risk in {"high", "critical"}:
            return {
                "check": "test_coverage",
                "status": "fail",
                "detail": f"No test evidence provided for tier={tier} risk={risk}. Required for T3+ or high-risk mutations.",
            }
        return {
            "check": "test_coverage",
            "status": "warn",
            "detail": "No test evidence; acceptable for T1/T2 low-risk mutations but recommended.",
        }
    return {
        "check": "test_coverage",
        "status": "pass",
        "detail": f"Test evidence present: {str(evidence)[:100]}",
    }


def check_confidence_threshold(mutation: dict) -> dict:
    """Verify confidence_score meets the tier's minimum threshold."""
    tier = str(mutation.get("tier", "T2")).upper()
    score = mutation.get("confidence_score")

    if score is None:
        return {
            "check": "confidence_threshold",
            "status": "warn",
            "detail": "No confidence_score declared; threshold check skipped.",
        }

    try:
        score = float(score)
    except (TypeError, ValueError):
        return {"check": "confidence_threshold", "status": "fail", "detail": f"Invalid confidence_score: {score!r}"}

    threshold = CONFIDENCE_THRESHOLDS.get(tier, 60.0)
    if score >= threshold:
        return {
            "check": "confidence_threshold",
            "status": "pass",
            "detail": f"Score {score} >= tier threshold {threshold} for {tier}.",
        }
    return {
        "check": "confidence_threshold",
        "status": "fail",
        "detail": f"Score {score} < tier threshold {threshold} for {tier}. Dispatch gate not met.",
    }


# ── Verdict logic ────────────────────────────────────────────────────────────


def compute_verdict(
    checks: list[dict],
    mutation: dict,
) -> tuple[str, dict | None]:
    """
    Compute final verdict from check results.

    Returns:
        verdict: "approve" | "reject" | "escalate"
        remediation_task: None or {"action": str, "reason": str}
    """
    tier = str(mutation.get("tier", "")).upper()
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]

    if not fails:
        if tier == "T4":
            # T4 always escalates to human, even with all-pass checks.
            return "escalate", {
                "action": "human_review_required",
                "reason": "T4 mutations require explicit human approval regardless of automated check results.",
            }
        if warns:
            return "approve", None  # Approve with warnings — caller should log them.
        return "approve", None

    # Any fail → reject with a remediation task.
    fail_summary = "; ".join(f["check"] for f in fails[:3])
    remediation = {
        "action": "open_remediation_task",
        "reason": f"Verification failed: {fail_summary}",
        "failed_checks": [f["check"] for f in fails],
    }

    # If tier is T4 or risk is critical, escalate rather than just reject.
    risk = str(mutation.get("risk_level", "medium")).lower()
    if tier == "T4" or risk == "critical":
        return "escalate", remediation

    return "reject", remediation


# ── Main verification flow ───────────────────────────────────────────────────


def verify(mutation: dict, dry_run: bool = False) -> dict:
    """Run all checks and produce the verdict record."""
    checks = [
        check_tier_gate(mutation),
        check_file_scope(mutation),
        check_forbidden_patterns(mutation),
        check_test_coverage(mutation),
        check_confidence_threshold(mutation),
    ]

    verdict, remediation = compute_verdict(checks, mutation)

    result: dict[str, Any] = {
        "verdict": verdict,
        "evidence": checks,
        "tier": str(mutation.get("tier", "unknown")).upper(),
        "mutation_id": str(mutation.get("id", "unknown")),
        "confidence_score": mutation.get("confidence_score"),
        "timestamp": _ts(),
        "dry_run": dry_run,
        "remediation_task": remediation,
    }
    return result


def write_audit(result: dict) -> Path:
    """Persist audit record to 07_LOGS_AND_AUDIT/verifier/."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts_safe = result["timestamp"].replace(":", "").replace("-", "")
    mid = str(result.get("mutation_id", "unknown")).replace("/", "_").replace(".", "_")
    path = AUDIT_DIR / f"{ts_safe}_{mid}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    # Also update latest.json for quick lookups.
    (AUDIT_DIR / "latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Independent verifier agent for T3+ mutations (GH #82)",
        epilog="Exit 0=approve, 1=reject, 2=escalate",
    )
    ap.add_argument("--mutation-file", required=False, help="Path to mutation JSON file")
    ap.add_argument("--dry-run", action="store_true", help="Run checks but do not write audit trail")
    ap.add_argument(
        "--example",
        action="store_true",
        help="Print an example mutation file schema and exit",
    )
    args = ap.parse_args()

    if args.example:
        example = {
            "id": "mut-001",
            "title": "Add policy engine rule evaluation",
            "tier": "T3",
            "confidence_score": 82.5,
            "allowed_files": ["scripts/", "docs/governance/"],
            "changed_files": ["scripts/policy_engine.py", "docs/governance/POLICY_ENGINE.md"],
            "forbidden_patterns": [],
            "test_evidence": "pytest tests/test_policy_engine.py: 8 passed",
            "risk_level": "medium",
            "author": "worker-epic-c",
            "timestamp": _ts(),
        }
        print(json.dumps(example, indent=2))
        return 0

    if not args.mutation_file:
        ap.print_help()
        return 1

    try:
        mutation = _load_mutation(args.mutation_file)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    result = verify(mutation, dry_run=args.dry_run)

    if not args.dry_run:
        audit_path = write_audit(result)
        result["_audit_path"] = str(audit_path.relative_to(REPO))

    print(json.dumps(result, indent=2))

    verdict = result["verdict"]
    if verdict == "approve":
        return 0
    if verdict == "reject":
        return 1
    # escalate
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
