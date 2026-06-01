#!/usr/bin/env python3
"""Agent performance-scoring and audit-telemetry module (bead gh-63).

Covers five eval requirements:
  1. Agent scorecards -- per-agent aggregates from input event records.
  2. False-positive tracking -- count + rate per agent.
  3. Task completion analytics -- completion_rate, failure_rate, performance_score.
  4. Audit trail correlation -- append each run to history.jsonl; classify_trend.
  5. Historical trend dashboard -- dashboard.md table + latest.json artifact.

Event shape:
  {agent: str, outcome: "completed"|"failed"|"abandoned",
   confidence: float, false_positive: bool}

Usage:
    python scripts/agent_scoring.py --events events.json
    python scripts/agent_scoring.py --events -          # stdin
    python scripts/agent_scoring.py --events events.json --json
    python scripts/agent_scoring.py --events events.json --strict
    python scripts/agent_scoring.py --timestamp 20260601T000000Z
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("AGENT_SCORING_REPO", str(Path(__file__).resolve().parents[1])))
ARTIFACT_DIR = Path(os.environ.get("AGENT_SCORING_ARTIFACT_DIR", str(REPO / "07_LOGS_AND_AUDIT" / "agent_scoring")))
HISTORY_FILE = ARTIFACT_DIR / "history.jsonl"
DASHBOARD_FILE = ARTIFACT_DIR / "dashboard.md"
LATEST_FILE = ARTIFACT_DIR / "latest.json"

AGENT_MIN_SCORE: int = int(os.environ.get("AGENT_MIN_SCORE", "0"))


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable)
# ---------------------------------------------------------------------------


def build_scorecard(events: list[dict]) -> dict:
    """Build per-agent scorecard from a list of event dicts.

    Returns:
        {agent_name: {tasks, completed, failed, abandoned, completion_rate,
                      failure_rate, avg_confidence,
                      false_positive_count, false_positive_rate}}
    """
    cards: dict[str, dict] = {}

    for ev in events:
        agent = str(ev.get("agent", "unknown"))
        outcome = str(ev.get("outcome", ""))
        confidence = float(ev.get("confidence", 0.0))
        fp = bool(ev.get("false_positive", False))

        if agent not in cards:
            cards[agent] = {
                "tasks": 0,
                "completed": 0,
                "failed": 0,
                "abandoned": 0,
                "confidence_sum": 0.0,
                "false_positive_count": 0,
            }

        c = cards[agent]
        c["tasks"] += 1
        c["confidence_sum"] += confidence
        if outcome == "completed":
            c["completed"] += 1
        elif outcome == "failed":
            c["failed"] += 1
        elif outcome == "abandoned":
            c["abandoned"] += 1
        if fp:
            c["false_positive_count"] += 1

    result: dict[str, dict] = {}
    for agent, c in cards.items():
        tasks = c["tasks"]
        completed = c["completed"]
        failed = c["failed"]
        abandoned = c["abandoned"]
        fp_count = c["false_positive_count"]
        result[agent] = {
            "tasks": tasks,
            "completed": completed,
            "failed": failed,
            "abandoned": abandoned,
            "completion_rate": round(completed / tasks, 4) if tasks else 0.0,
            "failure_rate": round(failed / tasks, 4) if tasks else 0.0,
            "avg_confidence": round(c["confidence_sum"] / tasks, 4) if tasks else 0.0,
            "false_positive_count": fp_count,
            "false_positive_rate": round(fp_count / tasks, 4) if tasks else 0.0,
        }

    return result


def performance_score(card: dict) -> int:
    """Compute a 0-100 performance score for a single agent card.

    Formula:
      base = completion_rate * 60          (0-60)
      conf = avg_confidence * 30           (0-30)
      fp   = (1 - false_positive_rate) * 10 (0-10)
      total = clamp(round(base + conf + fp), 0, 100)
    """
    base = card.get("completion_rate", 0.0) * 60.0
    conf = card.get("avg_confidence", 0.0) * 30.0
    fp_rate = card.get("false_positive_rate", 0.0)
    fp_bonus = (1.0 - fp_rate) * 10.0
    return max(0, min(100, round(base + conf + fp_bonus)))


def classify_trend(scores: list[float]) -> str:
    """Return 'improving', 'worsening', or 'stable' from ordered score list.

    Requires >= 2 entries; returns 'stable' for fewer.
    """
    if len(scores) < 2:
        return "stable"
    delta = scores[-1] - scores[-2]
    if delta > 0:
        return "improving"
    if delta < 0:
        return "worsening"
    return "stable"


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def _append_history(timestamp: str, per_agent_scores: dict[str, int]) -> None:
    """Append one scoring run to history.jsonl."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    entry = json.dumps({"timestamp": timestamp, "scores": per_agent_scores})
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(entry + "\n")


def _load_agent_history(agent: str) -> list[float]:
    """Load historical scores for a single agent from history.jsonl."""
    scores: list[float] = []
    if not HISTORY_FILE.exists():
        return scores
    try:
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return scores
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            s = entry.get("scores", {})
            if agent in s:
                scores.append(float(s[agent]))
        except Exception:  # noqa: BLE001
            pass
    return scores


def write_artifact(
    scorecard: dict,
    per_agent_scores: dict[str, int],
    timestamp: str,
) -> Path:
    """Write latest.json and a timestamped copy."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"timestamp": timestamp, "scorecard": scorecard, "scores": per_agent_scores},
        indent=2,
    )
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    LATEST_FILE.write_text(payload, encoding="utf-8")
    return LATEST_FILE


def write_dashboard(
    scorecard: dict,
    per_agent_scores: dict[str, int],
    timestamp: str,
) -> Path:
    """Write dashboard.md with an agents x score x trend table."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Agent Performance Dashboard",
        "",
        f"Generated: {timestamp}",
        "",
        "| Agent | Tasks | Completion | Failure | Avg Confidence | FP Rate | Score | Trend |",
        "|-------|-------|-----------|---------|----------------|---------|-------|-------|",
    ]

    for agent, card in sorted(scorecard.items()):
        hist = _load_agent_history(agent)
        trend = classify_trend(hist)
        score = per_agent_scores.get(agent, 0)
        lines.append(
            f"| {agent} "
            f"| {card['tasks']} "
            f"| {card['completion_rate']:.0%} "
            f"| {card['failure_rate']:.0%} "
            f"| {card['avg_confidence']:.2f} "
            f"| {card['false_positive_rate']:.0%} "
            f"| {score} "
            f"| {trend} |"
        )

    lines.append("")
    DASHBOARD_FILE.write_text("\n".join(lines), encoding="utf-8")
    return DASHBOARD_FILE


# ---------------------------------------------------------------------------
# summarize (fail-open)
# ---------------------------------------------------------------------------


def summarize() -> dict:
    """Compact summary for closeout report.  Never raises."""
    try:
        if not LATEST_FILE.exists():
            return {"status": "no_scan", "agents": 0, "top_agent": None, "lowest_agent": None}
        try:
            data = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {"status": "error", "agents": 0, "top_agent": None, "lowest_agent": None}
        scores: dict[str, int] = data.get("scores", {})
        if not scores:
            return {"status": "ok", "agents": 0, "top_agent": None, "lowest_agent": None}
        top = max(scores, key=lambda a: scores[a])
        low = min(scores, key=lambda a: scores[a])
        return {
            "status": "ok",
            "agents": len(scores),
            "top_agent": top,
            "lowest_agent": low,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "agents": 0, "top_agent": None, "lowest_agent": None}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_scoring(events: list[dict], timestamp: str) -> dict:
    """Full scoring pipeline; returns result dict."""
    scorecard = build_scorecard(events)
    per_agent_scores: dict[str, int] = {agent: performance_score(card) for agent, card in scorecard.items()}

    _append_history(timestamp, per_agent_scores)
    write_artifact(scorecard, per_agent_scores, timestamp)
    write_dashboard(scorecard, per_agent_scores, timestamp)

    return {
        "scorecard": scorecard,
        "scores": per_agent_scores,
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Agent performance-scoring module (gh-63)")
    ap.add_argument("--events", default=None, help="Path to JSON events file, or - for stdin")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default=None, help="Override ISO timestamp")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any agent is below AGENT_MIN_SCORE",
    )
    args = ap.parse_args()

    ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    events: list[dict] = []
    if args.events:
        try:
            if args.events == "-":
                raw = sys.stdin.read()
            else:
                raw = Path(args.events).read_text(encoding="utf-8")
            try:
                events = json.loads(raw)
            except Exception as exc:  # noqa: BLE001
                print(f"agent_scoring: failed to parse events JSON: {exc}")
                events = []
        except Exception as exc:  # noqa: BLE001
            print(f"agent_scoring: failed to read events: {exc}")
            events = []

    result = run_scoring(events, ts)

    print("agent scoring:")
    print(f"  agents scored: {len(result['scores'])}")
    for agent, score in sorted(result["scores"].items(), key=lambda kv: -kv[1]):
        card = result["scorecard"][agent]
        print(
            f"  {agent}: score={score}  tasks={card['tasks']}"
            f"  completion={card['completion_rate']:.0%}"
            f"  fp={card['false_positive_count']}"
        )
    print(f"  latest.json:   {LATEST_FILE}")
    print(f"  dashboard:     {DASHBOARD_FILE}")

    if args.json:
        print(json.dumps(result, indent=2))

    if args.strict:
        below = [a for a, s in result["scores"].items() if s < AGENT_MIN_SCORE]
        if below:
            print(f"agent_scoring: STRICT FAIL -- agents below {AGENT_MIN_SCORE}: {', '.join(below)}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
