#!/usr/bin/env python3
"""Coverage enforcement gate (bead gh-58 / chromatic-harness-v2).

Eval gates:
  1. Coverage threshold enforcement (COVERAGE_MIN env, default 0).
  2. Fail when coverage decreases beyond configured tolerance
     (COVERAGE_DROP_TOLERANCE env, default 2.0 pp).

Usage:
    python scripts/coverage_gate.py            # run coverage, exit 1 on fail
    python scripts/coverage_gate.py --json     # print full JSON result
    python scripts/coverage_gate.py --timestamp 20260601T000000Z
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "coverage"
BASELINE_FILE = ARTIFACT_DIR / "baseline.json"

# Eval 1: absolute minimum coverage (0 = do not hard-fail on absolute by default).
COVERAGE_MIN = float(os.environ.get("COVERAGE_MIN", "0"))
# Eval 2: allowed drop from baseline before failing (percentage points).
COVERAGE_DROP_TOLERANCE = float(os.environ.get("COVERAGE_DROP_TOLERANCE", "2.0"))


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def parse_coverage(text: str) -> float:
    """Parse a coverage percentage from pytest-cov terminal or JSON output.

    Accepts:
    - pytest-cov terminal line: "TOTAL   ... 72%"
    - coverage.py JSON dict with "totals": {"percent_covered": 72.3}
    - Plain numeric string "72.3"

    Returns the percentage as a float (0-100).
    Raises ValueError if no coverage value can be found.
    """
    # Try JSON first.
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # coverage.py --json format
            if "totals" in data and "percent_covered" in data["totals"]:
                return float(data["totals"]["percent_covered"])
            # pytest-cov JSON report format
            if "percent_covered" in data:
                return float(data["percent_covered"])
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    # pytest-cov terminal: "TOTAL    1234   456   63%"
    match = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", text, re.MULTILINE)
    if match:
        return float(match.group(1))

    # Generic "XX%" at end of a line (e.g. coverage report --show-missing).
    match = re.search(r"(\d+(?:\.\d+)?)%", text)
    if match:
        return float(match.group(1))

    raise ValueError("No coverage percentage found in output")


def _run(cmd: list[str], *, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, "tool-not-found"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except Exception as exc:
        return 1, str(exc)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def _pytest_cov_available() -> bool:
    """Return True if pytest-cov plugin is installed."""
    code, out = _run(
        [sys.executable, "-m", "pytest", "--co", "-q", "--co"],
        timeout=30,
    )
    # If pytest itself is missing we also degrade.
    if code == 127:
        return False
    code2, out2 = _run(
        [sys.executable, "-m", "pytest", "--co", "-q", "-p", "no:cacheprovider"],
        timeout=30,
    )
    # Try importing the plugin directly — fastest check.
    check_code, check_out = _run(
        [sys.executable, "-c", "import pytest_cov"],
        timeout=10,
    )
    return check_code == 0


def collect_coverage() -> dict:
    """Run pytest --cov and return a result dict with 'coverage' float.

    Degrades to status='not_instrumented' if pytest-cov is unavailable.
    Never returns a false pass.
    """
    if not _pytest_cov_available():
        return {
            "status": "not_instrumented",
            "coverage": None,
            "raw": "pytest-cov not available",
        }

    code, out = _run(
        [sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing", "-q"],
        timeout=300,
    )

    try:
        pct = parse_coverage(out)
        return {
            "status": "ok",
            "coverage": pct,
            "raw": out[-2000:],
            "exit_code": code,
        }
    except ValueError:
        return {
            "status": "parse_error",
            "coverage": None,
            "raw": out[-2000:],
            "exit_code": code,
        }


# ---------------------------------------------------------------------------
# Assessment (eval gates)
# ---------------------------------------------------------------------------


def _load_baseline() -> float | None:
    if BASELINE_FILE.exists():
        try:
            data = json.loads(BASELINE_FILE.read_text())
            return float(data["coverage"])
        except Exception:
            return None
    return None


def _save_baseline(coverage: float) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps({"coverage": coverage}))


def assess(collect_result: dict) -> dict:
    """Apply eval gates and return a full assessment dict."""
    status = collect_result.get("status", "unknown")
    coverage = collect_result.get("coverage")
    baseline = _load_baseline()

    # If not instrumented or parse error, degrade — never false pass.
    if status not in ("ok",) or coverage is None:
        return {
            "status": status,
            "passed": False,
            "coverage": None,
            "baseline": baseline,
            "threshold": COVERAGE_MIN,
            "drop_tolerance": COVERAGE_DROP_TOLERANCE,
            "fail_reason": f"coverage could not be determined (status={status})",
        }

    fail_reason: str | None = None

    # Eval 1: absolute threshold.
    if coverage < COVERAGE_MIN:
        fail_reason = f"coverage {coverage:.1f}% below minimum {COVERAGE_MIN:.1f}%"

    # Eval 2: regression vs baseline.
    if baseline is None:
        # First run — record and pass.
        _save_baseline(coverage)
        baseline = coverage
    else:
        drop = baseline - coverage
        if drop > COVERAGE_DROP_TOLERANCE and fail_reason is None:
            fail_reason = (
                f"coverage dropped {drop:.2f} pp "
                f"(from {baseline:.1f}% to {coverage:.1f}%, "
                f"tolerance {COVERAGE_DROP_TOLERANCE:.1f} pp)"
            )

    passed = fail_reason is None
    return {
        "status": "ok" if passed else "fail",
        "passed": passed,
        "coverage": coverage,
        "baseline": baseline,
        "threshold": COVERAGE_MIN,
        "drop_tolerance": COVERAGE_DROP_TOLERANCE,
        "fail_reason": fail_reason,
    }


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------


def write_artifact(result: dict, timestamp: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    latest = ARTIFACT_DIR / "latest.json"
    timestamped = ARTIFACT_DIR / f"coverage_{timestamp}.json"
    payload = json.dumps(result, indent=2)
    latest.write_text(payload)
    timestamped.write_text(payload)
    return latest


# ---------------------------------------------------------------------------
# Summarize (fail-open)
# ---------------------------------------------------------------------------


def summarize() -> dict:
    """Return a summary dict for the closeout report. Fail-open."""
    try:
        data = json.loads((ARTIFACT_DIR / "latest.json").read_text())
        return {
            "status": data.get("status", "unknown"),
            "passed": data.get("passed", True),
            "coverage": data.get("coverage"),
            "baseline": data.get("baseline"),
        }
    except Exception:
        return {"status": "unknown", "passed": True, "coverage": None, "baseline": None}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coverage enforcement gate")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    parser.add_argument("--timestamp", default=None, help="Override artifact timestamp")
    args = parser.parse_args(argv)

    ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    collect_result = collect_coverage()
    result = assess(collect_result)
    result["timestamp"] = ts
    write_artifact(result, ts)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        cov_str = f"{result['coverage']:.1f}%" if result["coverage"] is not None else "N/A"
        base_str = f"{result['baseline']:.1f}%" if result["baseline"] is not None else "none"
        print(
            f"[coverage-gate] coverage={cov_str} baseline={base_str} "
            f"min={COVERAGE_MIN:.1f}% drop_tol={COVERAGE_DROP_TOLERANCE:.1f}pp "
            f"passed={result['passed']}"
        )
        if not result["passed"]:
            print(f"  FAIL: {result.get('fail_reason', 'unknown')}")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
