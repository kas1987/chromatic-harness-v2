#!/usr/bin/env python3
"""
KPI Stub: Learning-application rate
Target: reads 07_LOGS_AND_AUDIT/learning_tiers/latest.json, counts applied (E1+) learnings.

Current state: 65 learnings indexed, all at E0 (baseline), none promoted to E1+.
A learning is "applied" when it has evidence_tier >= E1 (used in at least one session
and confirmed helpful). Promote learnings by running the learning tier scorer after
sessions where a learning was actively consulted.

Instrumentation needed:
  - After each session, run scripts/score_learning_tiers.py (or equivalent) to
    update evidence tiers based on session usage events.
  - Log learning slug + outcome in session telemetry so the scorer has signal.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEARNING_PATH = ROOT / "07_LOGS_AND_AUDIT" / "learning_tiers" / "latest.json"


def collect():
    try:
        data = json.loads(LEARNING_PATH.read_text(encoding="utf-8"))
        total = data.get("total_learnings", 0)
        pyramid = data.get("pyramid", {})
        applied = sum(sum(v.values()) for k, v in pyramid.items() if k != "E0")
        if total == 0:
            return {
                "kpi": "learning_application_rate",
                "value": None,
                "status": "not_instrumented",
                "note": "No learnings indexed yet",
            }
        rate = round(applied / total, 4)
        status = "ok" if applied > 0 else "not_instrumented"
        note = (
            f"{applied}/{total} learnings at E1+ evidence tier"
            if applied > 0
            else f"All {total} learnings at E0; none promoted — run score_learning_tiers.py post-session"
        )
        return {
            "kpi": "learning_application_rate",
            "value": rate if applied > 0 else None,
            "status": status,
            "note": note,
        }
    except FileNotFoundError:
        return {
            "kpi": "learning_application_rate",
            "value": None,
            "status": "not_instrumented",
            "note": "learning_tiers/latest.json not found",
        }
    except Exception as e:
        return {
            "kpi": "learning_application_rate",
            "value": None,
            "status": "error",
            "note": str(e),
        }


if __name__ == "__main__":
    print(json.dumps(collect()))
