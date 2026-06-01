#!/usr/bin/env python3
"""governance_review.py — single-entry governance orchestrator (gh-geov).

Chains the three governance modules built under the skqu epic into one
deterministic pipeline and writes a single composite artifact:

    policy_engine.evaluate(...)   -> policy decision (allow/block)
    ai_review_gate (heuristic)    -> risk score + findings + level
    review_consensus.build_result -> confidence-weighted final decision

The AI review level and the policy decision are each turned into a synthetic
reviewer verdict so the consensus engine produces one authoritative
final_decision over the whole governance signal.

Output contract (same as every other gate — see the artifact+summarize()
governance memory): writes 07_LOGS_AND_AUDIT/governance_review/latest.json +
a timestamped copy, and exposes a fail-open summarize() for the closeout
report and the release_readiness meta-gate.

Network-free: the only external calls are git diff (via ai_review_gate),
which fail-open to a clean diff when unavailable.

Usage:
    python scripts/governance_review.py [--json] [--base REF] [--timestamp TS]
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "governance_review"
LATEST_ARTIFACT = ARTIFACT_DIR / "latest.json"

DEFAULT_BASE = os.environ.get("GOVERNANCE_REVIEW_BASE", "origin/session/chromatic-harness-v2-initial")


# ---------------------------------------------------------------------------
# Module loading (load-by-path keeps these standalone scripts importable
# without a package install, matching the test convention used repo-wide).
# ---------------------------------------------------------------------------


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:  # pragma: no cover — defensive
        raise ImportError(name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Stage adapters — each returns a normalized dict and never raises.
# ---------------------------------------------------------------------------


def run_policy_stage(context: dict) -> dict:
    """Evaluate the active policy against a context. Fail-open to allow."""
    try:
        pe = _load("policy_engine")
        policy = pe.load_policy()
        return pe.evaluate(policy, context)
    except Exception as exc:  # noqa: BLE001
        return {"decision": "allow", "violations": [], "by_severity": {}, "error": str(exc)}


def run_ai_review_stage(base: str) -> dict:
    """Run the heuristic AI review gate over the diff. Fail-open to ok/0."""
    try:
        ar = _load("ai_review_gate")
        metrics = ar.collect_diff_metrics(base)
        findings = ar.generate_findings(metrics)
        score = ar.risk_score(metrics, findings)
        level = ar.classify_level(metrics.get("changed_files", 0), score)
        return {
            "risk_score": score,
            "level": level,
            "findings": findings,
            "changed_files": metrics.get("changed_files", 0),
        }
    except Exception as exc:  # noqa: BLE001
        return {"risk_score": 0, "level": "ok", "findings": [], "changed_files": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Signal -> reviewer synthesis (pure, testable)
# ---------------------------------------------------------------------------


def synthesize_reviews(policy: dict, ai_review: dict) -> list:
    """Turn the policy decision and AI review level into reviewer records the
    consensus engine consumes (reviewer/verdict/confidence/notes).

    Mapping:
      policy.decision  block -> reject (conf .9) ; allow -> approve (conf .7)
      ai_review.level  fail  -> reject (conf .85); warn -> abstain (conf .5);
                       ok    -> approve (conf .7)
    """
    reviews: list = []

    pdec = policy.get("decision", "allow")
    n_viol = len(policy.get("violations", []))
    reviews.append(
        {
            "reviewer": "policy_engine",
            "verdict": "reject" if pdec == "block" else "approve",
            "confidence": 0.9 if pdec == "block" else 0.7,
            "notes": f"{n_viol} policy violation(s)",
        }
    )

    level = ai_review.get("level", "ok")
    verdict = {"fail": "reject", "warn": "abstain", "ok": "approve"}.get(level, "approve")
    reviews.append(
        {
            "reviewer": "ai_review_gate",
            "verdict": verdict,
            "confidence": {"fail": 0.85, "warn": 0.5, "ok": 0.7}.get(level, 0.7),
            "notes": f"risk {ai_review.get('risk_score', 0)}/100, {len(ai_review.get('findings', []))} finding(s)",
        }
    )
    return reviews


def _default_context(ai_review: dict) -> dict:
    """Build a policy-evaluation context from AI-review metrics."""
    return {
        "changed_files": ai_review.get("changed_files", 0),
        "risk_score": ai_review.get("risk_score", 0),
        "findings_count": len(ai_review.get("findings", [])),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_review(base: str, context: dict | None = None) -> dict:
    """Run the full governance pipeline and return the composite result."""
    ai_review = run_ai_review_stage(base)
    ctx = context if context is not None else _default_context(ai_review)
    policy = run_policy_stage(ctx)

    reviews = synthesize_reviews(policy, ai_review)
    try:
        rc = _load("review_consensus")
        consensus = rc.build_result(reviews)
    except Exception as exc:  # noqa: BLE001
        consensus = {"final_decision": None, "escalation": True, "error": str(exc)}

    final = consensus.get("final_decision")
    # Decision precedence: a hard policy block is authoritative.
    if policy.get("decision") == "block":
        decision = "block"
    elif final == "reject":
        decision = "block"
    elif final is None:
        decision = "escalate"
    else:
        decision = "allow"

    return {
        "decision": decision,
        "policy": policy,
        "ai_review": ai_review,
        "consensus": consensus,
        "reviews": reviews,
    }


def write_artifact(result: dict, timestamp: str) -> Path:
    """Persist governance_review/latest.json + a timestamped copy."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    LATEST_ARTIFACT.write_text(payload, encoding="utf-8")
    return LATEST_ARTIFACT


# ---------------------------------------------------------------------------
# summarize (fail-open) — closeout + release_readiness consume this.
# ---------------------------------------------------------------------------


def summarize() -> dict:
    """Compact summary for the closeout report. Never raises."""
    try:
        if not LATEST_ARTIFACT.exists():
            return {"status": "no_scan", "decision": None}
        data = json.loads(LATEST_ARTIFACT.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "decision": data.get("decision"),
            "policy_decision": data.get("policy", {}).get("decision"),
            "ai_level": data.get("ai_review", {}).get("level"),
            "ai_risk_score": data.get("ai_review", {}).get("risk_score"),
            "final_decision": data.get("consensus", {}).get("final_decision"),
            "timestamp": data.get("timestamp"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "decision": None}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Governance review orchestrator (gh-geov)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="git base ref for the AI review diff")
    ap.add_argument("--json", action="store_true", help="print the full composite result as JSON")
    ap.add_argument("--timestamp", default="", help="override the artifact timestamp")
    args = ap.parse_args()

    ts = args.timestamp or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_review(args.base)
    artifact = write_artifact(result, ts)

    if args.json:
        print(json.dumps({**result, "timestamp": ts}, indent=2))
    else:
        print("Governance review:")
        print(f"  decision      : {result['decision'].upper()}")
        print(f"  policy        : {result['policy'].get('decision')}")
        print(
            f"  ai level      : {result['ai_review'].get('level')} (risk {result['ai_review'].get('risk_score')}/100)"
        )
        print(f"  consensus     : {result['consensus'].get('final_decision')}")
        print(f"  artifact      : {artifact}")

    # Exit non-zero only on a hard block; escalate/allow are advisory (fail-open
    # composition — the meta-gate decides ship/no-ship).
    return 1 if result["decision"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
