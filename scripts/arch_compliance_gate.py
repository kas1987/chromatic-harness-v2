#!/usr/bin/env python3
"""Architecture compliance + drift gate (bead gh-58 / area 3 of 3).

Covers two eval requirements:
  1. Repository structure compliance audit: verify EXPECTED_STRUCTURE entries exist.
  2. Architecture drift report: compare current top-level layout to a stored
     baseline (07_LOGS_AND_AUDIT/arch/baseline.json); report added/removed entries.

Exit codes: 0 = ok/warn, 1 = fail (required entry missing; or drift when --strict).

Usage:
    python scripts/arch_compliance_gate.py           # compliance + drift check
    python scripts/arch_compliance_gate.py --strict  # drift also fails the gate
    python scripts/arch_compliance_gate.py --json    # print full JSON result
    python scripts/arch_compliance_gate.py --timestamp 20260601T000000Z
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "arch"
BASELINE_FILE = ARTIFACT_DIR / "baseline.json"

# Eval 1: required top-level entries. All must exist for compliance to pass.
EXPECTED_STRUCTURE: list[str] = [
    "00_SOURCE_OF_TRUTH",
    "01_PROTOCOLS",
    "02_RUNTIME",
    "05_REPORTS",
    "07_LOGS_AND_AUDIT",
    "12_HANDOFFS",
    "scripts",
    "tests",
    "docs",
    "AGENT_OPERATIONS.md",
    "CLAUDE.md",
    "pyproject.toml",
]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def snapshot_structure(repo: Path) -> dict:
    """Return a dict of top-level entry names to their type (dir/file)."""
    result: dict[str, str] = {}
    for entry in repo.iterdir():
        if entry.name.startswith("."):
            continue
        result[entry.name] = "dir" if entry.is_dir() else "file"
    return result


def diff_structure(baseline: dict, current: dict) -> dict:
    """Pure function: compute added/removed top-level entries.

    Args:
        baseline: snapshot dict (name -> type) stored previously.
        current:  snapshot dict (name -> type) of the live repo.

    Returns:
        {"added": [...], "removed": [...]}
    """
    baseline_keys = set(baseline.keys())
    current_keys = set(current.keys())
    return {
        "added": sorted(current_keys - baseline_keys),
        "removed": sorted(baseline_keys - current_keys),
    }


def check_compliance(repo: Path) -> dict:
    """Eval 1: verify each EXPECTED_STRUCTURE entry exists under repo."""
    missing: list[str] = []
    for name in EXPECTED_STRUCTURE:
        if not (repo / name).exists():
            missing.append(name)
    return {
        "expected": EXPECTED_STRUCTURE,
        "missing": missing,
        "passed": len(missing) == 0,
    }


def check_drift(repo: Path, *, strict: bool = False) -> dict:
    """Eval 2: compare current structure to baseline; create baseline if absent."""
    current = snapshot_structure(repo)
    no_baseline = not BASELINE_FILE.exists()

    if no_baseline:
        # Record current state as baseline; no drift to report.
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return {
            "status": "baseline_created",
            "baseline_entries": len(current),
            "added": [],
            "removed": [],
            "drift_detected": False,
            "passed": True,
        }

    try:
        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "baseline_read_error",
            "error": str(exc),
            "added": [],
            "removed": [],
            "drift_detected": False,
            "passed": True,
        }

    diff = diff_structure(baseline, current)
    drift_detected = bool(diff["added"] or diff["removed"])
    # Drift is a warning by default; only fails when --strict.
    passed = not drift_detected or not strict

    return {
        "status": "ok",
        "added": diff["added"],
        "removed": diff["removed"],
        "drift_detected": drift_detected,
        "passed": passed,
    }


# ---------------------------------------------------------------------------
# Artifact + summarize
# ---------------------------------------------------------------------------


def write_artifact(result: dict, timestamp: str) -> Path:
    """Persist compliance+drift result as an artifact."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def summarize() -> dict:
    """Compact summary for the closeout report (reads latest artifact).
    Fail-open -- never raises."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "passed": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "passed": data.get("passed"),
            "missing": data.get("compliance", {}).get("missing", []),
            "drift_added": data.get("drift", {}).get("added", []),
            "drift_removed": data.get("drift", {}).get("removed", []),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "passed": None}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_gate(repo: Path, *, strict: bool = False) -> dict:
    compliance = check_compliance(repo)
    drift = check_drift(repo, strict=strict)
    passed = compliance["passed"] and drift["passed"]
    return {
        "compliance": compliance,
        "drift": drift,
        "passed": passed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Architecture compliance + drift gate (gh-58)")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Treat drift (added/removed top-level entries) as a gate failure",
    )
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default="", help="ISO timestamp override")
    args = ap.parse_args()

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_gate(REPO, strict=args.strict)
    artifact = write_artifact(result, ts)

    comp = result["compliance"]
    drift = result["drift"]

    print("arch compliance gate:")
    print(f"  required entries: {len(comp['expected'])} checked")
    if comp["missing"]:
        for m in comp["missing"]:
            print(f"    [MISSING] {m}")
    else:
        print("  compliance:       all required entries present")

    print(f"  drift status:     {drift.get('status', 'ok')}")
    if drift.get("added"):
        print(f"    added:   {', '.join(drift['added'])}")
    if drift.get("removed"):
        print(f"    removed: {', '.join(drift['removed'])}")
    if not drift.get("drift_detected"):
        print("  drift:            none detected")
    print(f"  artifact:         {artifact}")

    sep = "=" * 60
    status = "PASSED" if result["passed"] else "FAILED"
    print(f"\n{sep}\narch gate: {status}\n{sep}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
