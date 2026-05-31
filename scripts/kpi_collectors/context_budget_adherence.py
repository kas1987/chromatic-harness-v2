#!/usr/bin/env python3
"""
KPI Stub: Context-budget adherence
Target: counts sessions that compacted before reaching 65% context pressure.

Instrumentation needed:
  - Add context_pct_at_compact: float field to 05_REPORTS/telemetry.jsonl session entries.
  - This collector then counts rows where context_pct_at_compact < 65.0 (compliant)
    vs rows where it was missing or >= 65 (non-compliant or not yet compacted).
  - Also useful: track whether compaction was triggered (compacted: bool) so sessions
    that never compacted (short sessions) are correctly excluded from the denominator.

Current state: telemetry.jsonl has 3 rows; none contain context_pct_at_compact.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TELEMETRY_PATH = ROOT / "05_REPORTS" / "telemetry.jsonl"

THRESHOLD_PCT = 65.0


def collect():
    try:
        lines = [
            l.strip()
            for l in TELEMETRY_PATH.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        total = len(lines)
        compliant = 0
        instrumented = 0
        for line in lines:
            try:
                row = json.loads(line)
            except Exception:
                continue
            pct = row.get("context_pct_at_compact")
            if pct is not None:
                instrumented += 1
                if float(pct) < THRESHOLD_PCT:
                    compliant += 1
        if instrumented == 0:
            return {
                "kpi": "context_budget_adherence",
                "value": None,
                "status": "not_instrumented",
                "note": (
                    f"{total} telemetry rows found but none have context_pct_at_compact field. "
                    "Add context_pct_at_compact to session end telemetry writes."
                ),
            }
        rate = round(compliant / instrumented, 4)
        return {
            "kpi": "context_budget_adherence",
            "value": rate,
            "status": "ok",
            "note": f"{compliant}/{instrumented} sessions compacted before {THRESHOLD_PCT}% threshold",
        }
    except FileNotFoundError:
        return {
            "kpi": "context_budget_adherence",
            "value": None,
            "status": "not_instrumented",
            "note": "telemetry.jsonl not found",
        }
    except Exception as e:
        return {
            "kpi": "context_budget_adherence",
            "value": None,
            "status": "error",
            "note": str(e),
        }


if __name__ == "__main__":
    print(json.dumps(collect()))
