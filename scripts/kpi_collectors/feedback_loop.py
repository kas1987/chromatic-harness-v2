#!/usr/bin/env python3
"""KPI collector: KOS Stage 8 session-level feedback-loop metrics.

Reads 05_REPORTS/telemetry.jsonl and reports how many sessions triggered the
knowledge-feedback hook and how many new candidates were staged in total.

Emits:
  {
    "sessions_with_feedback": int,
    "total_candidates_from_feedback": int,
    "feedback_loop_pct": float,   # sessions_with_feedback / total_sessions * 100
    "status": "ok"
  }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TELEMETRY_FILE = REPO / "05_REPORTS" / "telemetry.jsonl"


def main() -> int:
    total_sessions = 0
    sessions_with_feedback = 0
    total_candidates_from_feedback = 0

    if TELEMETRY_FILE.exists():
        for raw in TELEMETRY_FILE.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue

            total_sessions += 1

            if record.get("event") == "knowledge_feedback":
                sessions_with_feedback += 1
                total_candidates_from_feedback += int(record.get("new_candidates", 0))

    feedback_loop_pct = (
        round(sessions_with_feedback / total_sessions * 100, 1)
        if total_sessions
        else 0.0
    )

    print(
        json.dumps(
            {
                "sessions_with_feedback": sessions_with_feedback,
                "total_candidates_from_feedback": total_candidates_from_feedback,
                "feedback_loop_pct": feedback_loop_pct,
                "status": "ok",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
