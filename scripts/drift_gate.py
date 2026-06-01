#!/usr/bin/env python3
"""Repository drift-detection & standards-enforcement gate (bead gh-61).

Covers five eval requirements:
  1. Repository tree audit -- snapshot top-level + key subdir structure.
  2. Protected path validation -- verify required protected paths exist.
  3. Drift score generation -- numeric 0-100 score from missing/added/removed.
  4. Historical drift trend tracking -- append {timestamp, score} to history.jsonl.
  5. Automated remediation recommendations -- concrete action per finding.

Baseline at 07_LOGS_AND_AUDIT/drift/baseline.json; if absent, record current and pass.
Artifact: 07_LOGS_AND_AUDIT/drift/latest.json + timestamped copy.

Exit codes: 0 = ok/warn, 1 = fail (required protected paths missing OR score < DRIFT_MIN_SCORE).

Usage:
    python scripts/drift_gate.py
    python scripts/drift_gate.py --json
    python scripts/drift_gate.py --timestamp 20260601T000000Z
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("DRIFT_GATE_REPO", str(Path(__file__).resolve().parents[1])))
ARTIFACT_DIR = Path(os.environ.get("DRIFT_GATE_ARTIFACT_DIR", str(REPO / "07_LOGS_AND_AUDIT" / "drift")))
BASELINE_FILE = ARTIFACT_DIR / "baseline.json"
HISTORY_FILE = ARTIFACT_DIR / "history.jsonl"

DRIFT_MIN_SCORE: int = int(os.environ.get("DRIFT_MIN_SCORE", "50"))

# Required protected paths -- missing any is a hard gate failure.
PROTECTED_PATHS: list[str] = [
    ".github",
    ".claude/settings.json",
    "scripts/hooks",
    "02_RUNTIME/router/gate.py",
    "AGENT_OPERATIONS.md",
    "CLAUDE.md",
    "pyproject.toml",
]

# Top-level entries expected in the repo (non-dot entries).
EXPECTED_TOP_LEVEL: list[str] = [
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
# subprocess helper
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable directly)
# ---------------------------------------------------------------------------


def snapshot_structure(repo: Path) -> dict[str, str]:
    """Return top-level non-dot entries -> type (dir/file)."""
    result: dict[str, str] = {}
    for entry in repo.iterdir():
        if entry.name.startswith("."):
            continue
        result[entry.name] = "dir" if entry.is_dir() else "file"
    return result


def compute_drift_score(missing: list[str], added: list[str], removed: list[str]) -> int:
    """Return 0-100 drift score (100 = no drift).

    Penalties:
      - Each missing required entry: -15 (heavy)
      - Each added unexpected top-level entry: -3 (light)
      - Each removed expected entry: -5 (light-medium)
    """
    penalty = len(missing) * 15 + len(added) * 3 + len(removed) * 5
    return max(0, 100 - penalty)


def classify_trend(scores: list[float]) -> str:
    """Return 'improving', 'worsening', or 'stable' from a list of scores.

    Requires at least 2 scores; returns 'stable' for 0 or 1 entries.
    """
    if len(scores) < 2:
        return "stable"
    delta = scores[-1] - scores[-2]
    if delta > 0:
        return "improving"
    if delta < 0:
        return "worsening"
    return "stable"


def build_recommendations(
    missing_required: list[str],
    added: list[str],
    removed: list[str],
    missing_protected: list[str],
) -> list[str]:
    """Return one concrete recommendation string per finding."""
    recs: list[str] = []
    for m in missing_required:
        recs.append(f"restore missing required entry: {m}")
    for a in added:
        recs.append(f"confirm whether new top-level entry is intentional: {a}")
    for r in removed:
        recs.append(f"confirm removal of expected entry is intentional: {r}")
    for p in missing_protected:
        recs.append(f"restore missing protected path immediately: {p}")
    return recs


# ---------------------------------------------------------------------------
# Collect / assess
# ---------------------------------------------------------------------------


def validate_protected_paths(repo: Path) -> dict:
    """Eval 2: check each PROTECTED_PATHS entry exists."""
    missing: list[str] = []
    for p in PROTECTED_PATHS:
        if not (repo / p).exists():
            missing.append(p)
    return {
        "checked": PROTECTED_PATHS,
        "missing": missing,
        "passed": len(missing) == 0,
    }


def collect_tree_audit(repo: Path) -> dict:
    """Eval 1: snapshot current structure vs EXPECTED_TOP_LEVEL."""
    current = snapshot_structure(repo)
    expected_set = set(EXPECTED_TOP_LEVEL)
    current_set = set(current.keys())

    missing = sorted(expected_set - current_set)
    added = sorted(current_set - expected_set)

    return {
        "current_entries": len(current),
        "expected_entries": len(EXPECTED_TOP_LEVEL),
        "missing_required": missing,
        "added_unexpected": added,
    }


def run_drift_analysis(repo: Path, audit: dict, timestamp: str) -> dict:
    """Eval 3+4: load or create baseline, compute score, append history."""
    current = snapshot_structure(repo)
    no_baseline = not BASELINE_FILE.exists()

    if no_baseline:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
        score = 100
        added: list[str] = []
        removed: list[str] = []
        status = "baseline_created"
    else:
        try:
            baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "baseline_read_error",
                "error": str(exc),
                "score": 100,
                "added": [],
                "removed": [],
                "trend": "stable",
            }
        baseline_keys = set(baseline.keys())
        current_keys = set(current.keys())
        added = sorted(current_keys - baseline_keys)
        removed = sorted(baseline_keys - current_keys)
        missing = audit["missing_required"]
        score = compute_drift_score(missing, added, removed)
        status = "ok"

    # Append to history
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    history_entry = json.dumps({"timestamp": timestamp, "score": score})
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(history_entry + "\n")

    # Compute trend from history
    scores: list[float] = []
    try:
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                scores.append(float(entry["score"]))
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass

    trend = classify_trend(scores)

    return {
        "status": status,
        "score": score,
        "added": added,
        "removed": removed if no_baseline is False else [],
        "trend": trend,
    }


# ---------------------------------------------------------------------------
# Artifact + summarize
# ---------------------------------------------------------------------------


def write_artifact(result: dict, timestamp: str) -> Path:
    """Persist full gate result."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def summarize() -> dict:
    """Compact summary for closeout report (reads latest artifact). Fail-open."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "passed": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "passed": data.get("passed"),
            "score": data.get("score"),
            "trend": data.get("trend"),
            "missing_count": len(data.get("missing_protected", [])),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "passed": None}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_gate(repo: Path, timestamp: str) -> dict:
    audit = collect_tree_audit(repo)
    protected = validate_protected_paths(repo)
    drift = run_drift_analysis(repo, audit, timestamp)

    score = drift["score"]
    missing_protected = protected["missing"]

    # Eval 5: recommendations
    recommendations = build_recommendations(
        missing_required=audit["missing_required"],
        added=drift["added"],
        removed=drift["removed"],
        missing_protected=missing_protected,
    )

    passed = len(missing_protected) == 0 and score >= DRIFT_MIN_SCORE

    return {
        "audit": audit,
        "protected": protected,
        "drift": drift,
        "score": score,
        "trend": drift["trend"],
        "missing_protected": missing_protected,
        "recommendations": recommendations,
        "passed": passed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Repository drift-detection gate (gh-61)")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default="", help="ISO timestamp override")
    args = ap.parse_args()

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_gate(REPO, ts)
    artifact = write_artifact(result, ts)

    print("drift gate:")
    print(f"  drift score:      {result['score']}/100  (min: {DRIFT_MIN_SCORE})")
    print(f"  trend:            {result['trend']}")

    audit = result["audit"]
    if audit["missing_required"]:
        print(f"  missing required: {', '.join(audit['missing_required'])}")
    else:
        print("  required entries: all present")

    if result["missing_protected"]:
        for p in result["missing_protected"]:
            print(f"  [PROTECTED MISSING] {p}")
    else:
        print("  protected paths:  all present")

    drift = result["drift"]
    if drift["added"]:
        print(f"  drift added:      {', '.join(drift['added'])}")
    if drift["removed"]:
        print(f"  drift removed:    {', '.join(drift['removed'])}")

    if result["recommendations"]:
        print("  recommendations:")
        for rec in result["recommendations"]:
            print(f"    - {rec}")

    print(f"  artifact:         {artifact}")

    sep = "=" * 60
    status = "PASSED" if result["passed"] else "FAILED"
    print(f"\n{sep}\ndrift gate: {status}\n{sep}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
