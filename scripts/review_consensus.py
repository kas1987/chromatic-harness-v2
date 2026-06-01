#!/usr/bin/env python3
"""Multi-agent review-consensus engine (bead gh-65).

Network-free, deterministic consensus over a set of *independent agent reviews*
supplied as INPUT data (a list of review dicts) -- NOT live LLM calls.  The
engine validates the reviews, computes a confidence-weighted consensus, applies
a tie-break / escalation path, persists an audit artifact, and integrates an
optional final human approval.

Covers the five eval requirements of bead gh-65:
  1. Independent agent reviews -- review record shape + normalize_reviews().
  2. Consensus scoring model   -- compute_consensus() weighted vote.
  3. Tie-break and escalation  -- resolve_tie() + tie-band detection.
  4. Review artifact persistence (07_LOGS_AND_AUDIT/review_consensus/).
  5. Human approval integration -- apply_human_approval(), required on escalation.

Usage:
    python scripts/review_consensus.py --reviews reviews.json
    cat reviews.json | python scripts/review_consensus.py --reviews -
    python scripts/review_consensus.py --reviews r.json --approver alice --human-decision approve

Exit codes: 0 = approve (or human-approved), 1 = reject / escalated-unresolved.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "review_consensus"

VALID_VERDICTS = ("approve", "reject", "abstain")

# Eval 3: score magnitude at-or-below this (absolute) band counts as a tie.
CONSENSUS_TIE_BAND = float(os.environ.get("CONSENSUS_TIE_BAND", "0.1"))


# ---------------------------------------------------------------------------
# Eval 1: review records + normalization
# ---------------------------------------------------------------------------


def _clamp_confidence(value: object) -> float:
    """Coerce a confidence to a float in [0, 1]; default 0.5 on bad input."""
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.5
    if c != c:  # NaN guard
        return 0.5
    return max(0.0, min(1.0, c))


def normalize_reviews(raw: list) -> list:
    """Validate/clean a raw list of review dicts.

    Review record shape:
        {reviewer: str, verdict: "approve"|"reject"|"abstain",
         confidence: float 0..1, notes: str}

    Rules:
      - Non-dict entries are dropped.
      - Unknown/missing verdicts are coerced to "abstain".
      - Confidence is clamped to [0, 1] (bad/missing -> 0.5).
      - reviewer defaults to "anonymous"; notes default to "".
    """
    cleaned: list = []
    if not isinstance(raw, list):
        return cleaned
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        verdict = str(entry.get("verdict", "")).strip().lower()
        if verdict not in VALID_VERDICTS:
            verdict = "abstain"
        reviewer = entry.get("reviewer")
        reviewer = str(reviewer).strip() if reviewer not in (None, "") else f"reviewer-{idx}"
        notes = entry.get("notes", "")
        notes = str(notes) if notes is not None else ""
        cleaned.append(
            {
                "reviewer": reviewer,
                "verdict": verdict,
                "confidence": _clamp_confidence(entry.get("confidence")),
                "notes": notes,
            }
        )
    return cleaned


# ---------------------------------------------------------------------------
# Eval 2: consensus scoring model
# ---------------------------------------------------------------------------


def compute_consensus(reviews: list) -> dict:
    """Confidence-weighted vote over normalized reviews.

    approve contributes +confidence, reject contributes +confidence to its side,
    abstain contributes nothing.  Score is normalized to [-1, 1]:

        score = (approve_weight - reject_weight) / (approve_weight + reject_weight)

    Returns {score, approve_weight, reject_weight, verdict}.
    verdict is "approve" (score > band), "reject" (score < -band), else "tie".
    """
    approve_weight = 0.0
    reject_weight = 0.0
    for r in reviews:
        verdict = r.get("verdict")
        conf = _clamp_confidence(r.get("confidence"))
        if verdict == "approve":
            approve_weight += conf
        elif verdict == "reject":
            reject_weight += conf
        # abstain -> ignored

    total = approve_weight + reject_weight
    score = 0.0 if total == 0 else (approve_weight - reject_weight) / total

    if score > CONSENSUS_TIE_BAND:
        verdict = "approve"
    elif score < -CONSENSUS_TIE_BAND:
        verdict = "reject"
    else:
        verdict = "tie"

    return {
        "score": round(score, 6),
        "approve_weight": round(approve_weight, 6),
        "reject_weight": round(reject_weight, 6),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Eval 3: tie-break and escalation
# ---------------------------------------------------------------------------


def resolve_tie(consensus: dict, reviews: list) -> dict:
    """Break a tie or escalate.

    Tie when consensus verdict is "tie" (score within +/- CONSENSUS_TIE_BAND of 0).
    Resolution: the highest-confidence non-abstain reviewer's verdict wins, but
    only if a clear winner exists (single max confidence, non-tie verdict).  If
    no decisive reviewer exists, escalate to a human.

    Returns {escalation: bool, escalation_reason: str|None,
             tie_break_verdict: "approve"|"reject"|None, tie_break_by: str|None}.
    """
    is_tie = consensus.get("verdict") == "tie" or abs(consensus.get("score", 0.0)) <= CONSENSUS_TIE_BAND

    if not is_tie:
        return {
            "escalation": False,
            "escalation_reason": None,
            "tie_break_verdict": None,
            "tie_break_by": None,
        }

    decisive = [r for r in reviews if r.get("verdict") in ("approve", "reject")]
    if not decisive:
        return {
            "escalation": True,
            "escalation_reason": "tie with no decisive (non-abstain) reviewers",
            "tie_break_verdict": None,
            "tie_break_by": None,
        }

    top_conf = max(_clamp_confidence(r.get("confidence")) for r in decisive)
    leaders = [r for r in decisive if _clamp_confidence(r.get("confidence")) == top_conf]
    leader_verdicts = {r.get("verdict") for r in leaders}

    if len(leader_verdicts) == 1:
        winner = leaders[0]
        return {
            "escalation": False,
            "escalation_reason": None,
            "tie_break_verdict": winner["verdict"],
            "tie_break_by": winner["reviewer"],
        }

    # Highest-confidence reviewers disagree -> escalate to human.
    return {
        "escalation": True,
        "escalation_reason": "tie unbroken: highest-confidence reviewers disagree",
        "tie_break_verdict": None,
        "tie_break_by": None,
    }


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------


def build_result(raw_reviews: list) -> dict:
    """Full pipeline: normalize -> consensus -> tie/escalation -> final decision.

    final_decision is one of "approve"/"reject"/None.  It is None whenever the
    review is escalated and not yet human-approved (eval 5 requirement).
    """
    reviews = normalize_reviews(raw_reviews)
    consensus = compute_consensus(reviews)
    tie = resolve_tie(consensus, reviews)

    escalation = bool(tie["escalation"])
    final_decision: str | None
    if consensus["verdict"] in ("approve", "reject"):
        final_decision = consensus["verdict"]
    elif tie["tie_break_verdict"] in ("approve", "reject"):
        final_decision = tie["tie_break_verdict"]
    else:
        final_decision = None  # escalated, awaiting human

    return {
        "reviews": reviews,
        "consensus": consensus,
        "escalation": escalation,
        "escalation_reason": tie["escalation_reason"],
        "tie_break": {
            "verdict": tie["tie_break_verdict"],
            "by": tie["tie_break_by"],
        },
        "human_approval": None,
        "final_decision": final_decision,
    }


# ---------------------------------------------------------------------------
# Eval 5: human approval integration
# ---------------------------------------------------------------------------


def apply_human_approval(result: dict, approver: str, decision: str) -> dict:
    """Record a final, auditable human approve/reject decision.

    A human decision is authoritative: it sets final_decision unconditionally and
    clears the escalation flag.  Required to finalize any escalated review.
    Returns the same result dict (mutated in place) for convenience.
    """
    decision = str(decision).strip().lower()
    if decision not in ("approve", "reject"):
        raise ValueError(f"human decision must be approve|reject, got {decision!r}")

    result["human_approval"] = {
        "approver": str(approver),
        "decision": decision,
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    }
    result["final_decision"] = decision
    result["escalation"] = False
    result["escalation_reason"] = None
    return result


# ---------------------------------------------------------------------------
# Eval 4: artifact persistence
# ---------------------------------------------------------------------------


def write_artifact(result: dict, timestamp: str) -> Path:
    """Persist review_consensus/latest.json + timestamped copy."""
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
            return {
                "status": "no_report",
                "verdict": None,
                "score": None,
                "escalation": None,
                "final_decision": None,
            }
        data = json.loads(latest.read_text(encoding="utf-8"))
        consensus = data.get("consensus", {}) if isinstance(data.get("consensus"), dict) else {}
        return {
            "status": "ok",
            "verdict": consensus.get("verdict"),
            "score": consensus.get("score"),
            "escalation": data.get("escalation"),
            "final_decision": data.get("final_decision"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "verdict": None,
            "score": None,
            "escalation": None,
            "final_decision": None,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_reviews(source: str) -> list:
    """Read raw reviews from a JSON file path or '-' for stdin (fail-open to [])."""
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception:  # noqa: BLE001 — missing/corrupt/partial input
        return []
    if isinstance(data, dict) and isinstance(data.get("reviews"), list):
        return data["reviews"]
    return data if isinstance(data, list) else []


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-agent review-consensus engine (gh-65)")
    ap.add_argument("--reviews", required=True, help="JSON file of review records, or '-' for stdin")
    ap.add_argument("--approver", default=None, help="Human approver id (with --human-decision)")
    ap.add_argument("--human-decision", default=None, choices=["approve", "reject"], help="Final human decision")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default=None, help="Override timestamp (ISO-8601 compact)")
    args = ap.parse_args()

    ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw = _load_reviews(args.reviews)
    result = build_result(raw)

    if args.human_decision:
        apply_human_approval(result, args.approver or "human", args.human_decision)

    artifact = write_artifact(result, ts)
    consensus = result["consensus"]

    if args.json:
        print(json.dumps({**result, "timestamp": ts}, indent=2))
    else:
        print("Review consensus:")
        print(f"  reviewers:   {len(result['reviews'])}")
        print(f"  verdict:     {consensus['verdict'].upper()}  (score={consensus['score']})")
        print(f"  weights:     approve={consensus['approve_weight']} reject={consensus['reject_weight']}")
        if result["escalation"]:
            print(f"  ESCALATED:   {result['escalation_reason']}")
        tb = result["tie_break"]
        if tb["verdict"]:
            print(f"  tie-break:   {tb['verdict']} by {tb['by']}")
        if result["human_approval"]:
            ha = result["human_approval"]
            print(f"  human:       {ha['decision']} by {ha['approver']}")
        print(f"  final:       {result['final_decision']}")
        print(f"  artifact:    {artifact}")

    # Exit 0 only when finally approved; reject or unresolved escalation -> 1.
    return 0 if result["final_decision"] == "approve" else 1


if __name__ == "__main__":
    sys.exit(main())
