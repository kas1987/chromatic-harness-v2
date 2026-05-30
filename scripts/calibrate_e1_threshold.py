#!/usr/bin/env python3
"""Weekly E1 threshold calibration review for learning tiers.

Run after compute_learning_tiers.py to assess tier health and apply the
two-cycle rebalance rubric when enough calibration history exists.

Usage:
    python scripts/calibrate_e1_threshold.py            # full run
    python scripts/calibrate_e1_threshold.py --dry-run  # report only, no writes
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO / "config" / "learning_tier_policy.json"
TIER_REPORT = REPO / "07_LOGS_AND_AUDIT" / "learning_tiers" / "latest.json"
CYCLES_DIR = REPO / ".agents" / "audit" / "calibration-cycles"

E1_SCORE_FLOOR = 0.28
E1_SCORE_CEILING = 0.45
E1_SCORE_STEP = 0.02
GRADUATION_RATE_LOW = 0.05
GRADUATION_RATE_HIGH = 0.30
NEAR_BOUNDARY_WINDOW = 0.05
MIN_NEAR_E1_COUNT = 3
MIN_DAYS_BETWEEN_CYCLES = 7


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _load_policy() -> dict[str, Any]:
    policy = _load_json(POLICY_PATH, {})
    if not policy:
        print(f"ERROR: policy file not found or empty: {POLICY_PATH}", file=sys.stderr)
        sys.exit(1)
    return policy


def _load_tier_report() -> dict[str, Any]:
    report = _load_json(TIER_REPORT, {})
    if not report:
        print(
            f"ERROR: tier report not found. Run compute_learning_tiers.py first: {TIER_REPORT}",
            file=sys.stderr,
        )
        sys.exit(1)
    return report


def _list_prior_cycles() -> list[Path]:
    if not CYCLES_DIR.is_dir():
        return []
    return sorted(CYCLES_DIR.glob("????-??-??-calibration.json"))


def _days_since_last_cycle(cycles: list[Path]) -> float | None:
    if not cycles:
        return None
    last = cycles[-1]
    try:
        artifact = json.loads(last.read_text(encoding="utf-8"))
        last_date_str = artifact.get("date") or ""
        last_date = datetime.strptime(last_date_str[:10], "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)
        return (now - last_date).total_seconds() / 86400.0
    except Exception:
        return None


def _compute_metrics(report: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pyramid = report.get("pyramid") or {}
    e0_counts = pyramid.get("E0") or {}
    e1_counts = pyramid.get("E1") or {}
    e0_total = sum(e0_counts.values())
    e1_total = sum(e1_counts.values())

    e1_rule = (policy.get("tiers") or {}).get("E1") or {}
    e1_min_score = float(e1_rule.get("min_score") or 0.32)

    items = report.get("items") or []
    near_e1_count = sum(
        1
        for item in items
        if item.get("evidence_tier") == "E0"
        and (e1_min_score - NEAR_BOUNDARY_WINDOW)
        <= float(item.get("score") or 0.0)
        < e1_min_score
    )

    avg_score_e0 = 0.0
    e0_items = [item for item in items if item.get("evidence_tier") == "E0"]
    if e0_items:
        avg_score_e0 = sum(float(i.get("score") or 0.0) for i in e0_items) / len(
            e0_items
        )

    total_el = e0_total + e1_total
    graduation_rate = (e1_total / total_el) if total_el > 0 else 0.0

    return {
        "e0_total": e0_total,
        "e1_total": e1_total,
        "near_e1_count": near_e1_count,
        "graduation_rate": round(graduation_rate, 4),
        "avg_score_e0": round(avg_score_e0, 4),
        "e1_min_score": e1_min_score,
    }


def _decide_rebalance(metrics: dict[str, Any]) -> tuple[str, str, float]:
    """Return (decision, rationale, new_threshold)."""
    e1_min = metrics["e1_min_score"]
    grad = metrics["graduation_rate"]
    near = metrics["near_e1_count"]

    if grad < GRADUATION_RATE_LOW and near >= MIN_NEAR_E1_COUNT:
        new_score = max(E1_SCORE_FLOOR, round(e1_min - E1_SCORE_STEP, 4))
        if new_score == e1_min:
            return (
                "NO_CHANGE",
                f"graduation_rate={grad:.3f} is low but e1_min_score already at floor {E1_SCORE_FLOOR}",
                e1_min,
            )
        return (
            "LOWER",
            f"graduation_rate={grad:.3f} < {GRADUATION_RATE_LOW} and near_e1_count={near} >= {MIN_NEAR_E1_COUNT}: "
            f"too many learnings stranded near E1 boundary",
            new_score,
        )

    if grad > GRADUATION_RATE_HIGH and e1_min < E1_SCORE_CEILING:
        new_score = min(E1_SCORE_CEILING, round(e1_min + E1_SCORE_STEP, 4))
        return (
            "RAISE",
            f"graduation_rate={grad:.3f} > {GRADUATION_RATE_HIGH}: "
            f"E1 threshold too permissive, learnings graduating too easily",
            new_score,
        )

    return (
        "NO_CHANGE",
        f"graduation_rate={grad:.3f} within acceptable band [{GRADUATION_RATE_LOW}, {GRADUATION_RATE_HIGH}]",
        e1_min,
    )


def _apply_threshold(policy: dict[str, Any], new_score: float) -> None:
    policy.setdefault("tiers", {}).setdefault("E1", {})["min_score"] = new_score
    POLICY_PATH.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_audit(
    cycle_num: int,
    date_str: str,
    metrics: dict[str, Any],
    decision: str,
    rationale: str,
    new_threshold: float,
    dry_run: bool,
) -> Path:
    artifact = {
        "cycle_number": cycle_num,
        "date": date_str,
        "before_threshold": metrics["e1_min_score"],
        "after_threshold": new_threshold,
        "graduation_rate": metrics["graduation_rate"],
        "near_e1_count": metrics["near_e1_count"],
        "e0_total": metrics["e0_total"],
        "e1_total": metrics["e1_total"],
        "avg_score_e0": metrics["avg_score_e0"],
        "decision": decision,
        "rationale": rationale,
        "dry_run": dry_run,
    }
    fname = CYCLES_DIR / f"{date_str}-calibration.json"
    if not dry_run:
        CYCLES_DIR.mkdir(parents=True, exist_ok=True)
        fname.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return fname


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report metrics and rebalance decision without writing files",
    )
    args = parser.parse_args()

    policy = _load_policy()
    report = _load_tier_report()
    metrics = _compute_metrics(report, policy)
    prior_cycles = _list_prior_cycles()
    cycle_num = len(prior_cycles) + 1
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("=== Learning Tier Calibration Review ===")
    print(f"Cycle:              {cycle_num}")
    print(f"Date:               {date_str}")
    print(f"E0 total:           {metrics['e0_total']}")
    print(f"E1 total:           {metrics['e1_total']}")
    print(f"Near-E1 (±0.05):    {metrics['near_e1_count']}")
    print(f"Graduation rate:    {metrics['graduation_rate']:.3f}")
    print(f"Avg E0 score:       {metrics['avg_score_e0']:.4f}")
    print(f"E1 min_score now:   {metrics['e1_min_score']}")
    print()

    days_since = _days_since_last_cycle(prior_cycles)
    rebalance_eligible = len(prior_cycles) >= 2 and (
        days_since is None or days_since >= MIN_DAYS_BETWEEN_CYCLES
    )

    if not rebalance_eligible:
        remaining = max(0, 2 - len(prior_cycles))
        print(
            f"Rebalance: NOT ELIGIBLE "
            f"(cycles_completed={len(prior_cycles)}, need 2; "
            f"{'days_since_last={:.1f}'.format(days_since) if days_since is not None else 'first run'})"
        )
        if remaining > 0:
            print(
                f"  -> Complete {remaining} more calibration cycle(s) to unlock rebalance."
            )
        decision, rationale, new_threshold = (
            "NO_CHANGE",
            "rebalance not yet eligible",
            metrics["e1_min_score"],
        )
    else:
        decision, rationale, new_threshold = _decide_rebalance(metrics)
        print(f"Rebalance decision: {decision}")
        print(f"Rationale:          {rationale}")
        if decision != "NO_CHANGE":
            print(f"Threshold change:   {metrics['e1_min_score']} → {new_threshold}")
        if not args.dry_run and decision != "NO_CHANGE":
            _apply_threshold(policy, new_threshold)
            print(f"Applied:            {POLICY_PATH.relative_to(REPO)}")

    artifact_path = _write_audit(
        cycle_num, date_str, metrics, decision, rationale, new_threshold, args.dry_run
    )
    if args.dry_run:
        print(f"\n[dry-run] Audit artifact would be: {artifact_path.relative_to(REPO)}")
    else:
        print(f"\nAudit artifact:     {artifact_path.relative_to(REPO)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
