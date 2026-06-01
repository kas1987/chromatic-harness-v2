#!/usr/bin/env python3
"""Release-readiness report and go/no-go gate (bead gh-62).

Aggregates sibling gate artifacts (security, coverage, pr_risk, preflight, arch)
into a single quality score, security score, blocker inventory, and a GO/NO-GO
release decision.

Usage:
    python scripts/release_readiness.py          # run gate, exit 1 on NO-GO
    python scripts/release_readiness.py --json   # print full JSON result
    python scripts/release_readiness.py --timestamp 20260601T000000Z
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "release"

# Sibling gate artifact paths (best-effort reads; missing => "unknown").
_ARTIFACT_PATHS: dict[str, Path] = {
    "security": REPO / "07_LOGS_AND_AUDIT" / "security" / "latest.json",
    "coverage": REPO / "07_LOGS_AND_AUDIT" / "coverage" / "latest.json",
    "pr_risk": REPO / "07_LOGS_AND_AUDIT" / "pr_risk" / "latest.json",
    "preflight": REPO / "07_LOGS_AND_AUDIT" / "preflight" / "latest.json",
    "arch": REPO / "07_LOGS_AND_AUDIT" / "arch" / "latest.json",
}

# Penalty per high-severity security finding (security_score).
SEC_HIGH_SEV_PENALTY = int(os.environ.get("RELEASE_SEC_HIGH_SEV_PENALTY", "25"))


# ---------------------------------------------------------------------------
# Artifact loading (fail-open per file)
# ---------------------------------------------------------------------------


def load_inputs(paths: dict[str, Path] | None = None) -> dict[str, dict]:
    """Load all gate artifacts.  Missing or corrupt files return {"_missing": True}."""
    if paths is None:
        paths = _ARTIFACT_PATHS
    inputs: dict[str, dict] = {}
    for key, path in paths.items():
        try:
            text = path.read_text(encoding="utf-8")
            inputs[key] = json.loads(text)
        except FileNotFoundError:
            inputs[key] = {"_missing": True}
        except Exception:  # noqa: BLE001 — partially written, corrupt, etc.
            inputs[key] = {"_missing": True}
    return inputs


# ---------------------------------------------------------------------------
# Pure scoring / aggregation functions
# ---------------------------------------------------------------------------


def quality_score(inputs: dict) -> int:
    """Combine preflight (lint+tests), coverage, and arch into a 0-100 score.

    Weights:
      preflight passed  -> 40 pts
      coverage passed   -> 35 pts
      arch passed       -> 25 pts

    Each sub-score is 0 if the gate failed or data is unknown.
    """
    score = 0

    pre = inputs.get("preflight", {})
    if not pre.get("_missing") and pre.get("passed") is True:
        score += 40

    cov = inputs.get("coverage", {})
    if not cov.get("_missing") and cov.get("passed") is True:
        score += 35

    arch = inputs.get("arch", {})
    if not arch.get("_missing") and arch.get("passed") is True:
        score += 25

    return score


def security_score(sec: dict) -> int:
    """Derive a 0-100 security score from security/latest.json.

    100 if passed and no high-severity findings.
    Drops SEC_HIGH_SEV_PENALTY points per high-severity finding (floor 0).
    0 if the gate failed outright.
    """
    if sec.get("_missing"):
        return 0
    if not sec.get("passed", False):
        return 0
    high = int(sec.get("high_severity_total", 0))
    return max(0, 100 - high * SEC_HIGH_SEV_PENALTY)


def collect_blockers(inputs: dict) -> list[dict]:
    """List every input gate currently failing.

    Each entry: {"gate": str, "reason": str}.
    Also appends open P0/P1 beads (best-effort; skipped if bd unavailable).
    """
    blockers: list[dict] = []

    def _check(key: str, label: str) -> None:
        gate = inputs.get(key, {})
        if gate.get("_missing"):
            return  # unknown => not a blocker (fail-open)
        if not gate.get("passed", True):
            blockers.append({"gate": key, "reason": f"{label} gate failed"})

    _check("security", "Security")
    _check("coverage", "Coverage")
    _check("preflight", "Preflight")
    _check("arch", "Architecture")

    pr = inputs.get("pr_risk", {})
    if not pr.get("_missing") and pr.get("risk_level") == "fail":
        blockers.append({"gate": "pr_risk", "reason": "PR risk gate at FAIL level"})

    # Open P0/P1 beads (best-effort).
    try:
        r = subprocess.run(
            ["bd", "list", "--status", "open", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=REPO,
        )
        if r.returncode == 0 and r.stdout.strip():
            beads = json.loads(r.stdout)
            for b in beads if isinstance(beads, list) else []:
                priority = str(b.get("priority", "")).upper()
                if priority in ("P0", "P1"):
                    blockers.append(
                        {
                            "gate": "bead",
                            "reason": f"Open {priority} bead: {b.get('id')} {b.get('title', '')}".strip(),
                        }
                    )
    except Exception:  # noqa: BLE001
        pass  # bd unavailable or output not JSON — skip silently

    return blockers


def coverage_summary(inputs: dict) -> dict:
    """Surface pass/fail, coverage%, and baseline for the report."""
    cov = inputs.get("coverage", {})
    if cov.get("_missing"):
        return {"status": "unknown"}
    return {
        "passed": cov.get("passed"),
        "coverage": cov.get("coverage"),
        "baseline": cov.get("baseline"),
        "status": "ok",
    }


def make_report(inputs: dict) -> dict:
    """Build the full release-readiness report dict."""
    qs = quality_score(inputs)
    ss = security_score(inputs.get("security", {"_missing": True}))
    blockers = collect_blockers(inputs)
    decision = "GO" if not blockers else "NO-GO"
    return {
        "quality_score": qs,
        "security_score": ss,
        "coverage": coverage_summary(inputs),
        "blockers": blockers,
        "blocker_count": len(blockers),
        "decision": decision,
        "passed": decision == "GO",
    }


# ---------------------------------------------------------------------------
# Artifact write
# ---------------------------------------------------------------------------


def write_artifact(result: dict, timestamp: str) -> Path:
    """Write release/latest.json + timestamped copy."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


# ---------------------------------------------------------------------------
# summarize (fail-open)
# ---------------------------------------------------------------------------


def summarize() -> dict:
    """Compact summary for the closeout report.  Never raises."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_report", "decision": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "decision": data.get("decision"),
            "quality_score": data.get("quality_score"),
            "security_score": data.get("security_score"),
            "blocker_count": data.get("blocker_count", 0),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "decision": None}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Release-readiness gate (gh-62)")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default=None, help="Override timestamp (ISO-8601 compact)")
    args = ap.parse_args()

    ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    inputs = load_inputs()
    report = make_report(inputs)
    artifact = write_artifact(report, ts)

    if args.json:
        print(json.dumps({**report, "timestamp": ts}, indent=2))
    else:
        d = report["decision"]
        qs = report["quality_score"]
        ss = report["security_score"]
        print(f"Release readiness: {d}  (quality={qs}/100  security={ss}/100)")
        cov = report["coverage"]
        if cov.get("status") == "ok":
            pct = cov.get("coverage")
            base = cov.get("baseline")
            print(f"  Coverage: {'PASS' if cov.get('passed') else 'FAIL'}  {pct}%  (baseline {base}%)")
        if report["blockers"]:
            print(f"  Blockers ({report['blocker_count']}):")
            for b in report["blockers"]:
                print(f"    [{b['gate']}] {b['reason']}")
        print(f"  Artifact: {artifact}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
