#!/usr/bin/env python3
"""
KPI Stub: Cache-hit rate
Target: reads model invocation logs, computes cache_hits / total_calls.

Instrumentation needed:
  - Log cache_hit: true/false on every LLM call in scripts/session_context_report.py
    or wherever model invocations are recorded (likely 07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl).
  - Fields to add: {"cache_hit": bool, "provider": str, "model": str, "timestamp": str}
  - Then this collector sums cache_hit==true / total rows.

Current status: AGENT_RUN_LOG.jsonl has 1 line; no cache_hit field present.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_PATH = ROOT / "07_LOGS_AND_AUDIT" / "AGENT_RUN_LOG.jsonl"


def collect():
    try:
        lines = [
            l.strip()
            for l in LOG_PATH.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        total = len(lines)
        hits = sum(1 for l in lines if json.loads(l).get("cache_hit") is True)
        if total == 0 or hits == 0:
            return {
                "kpi": "cache_hit_rate",
                "value": None,
                "status": "not_instrumented",
                "note": "Add cache_hit:bool field to AGENT_RUN_LOG.jsonl entries",
            }
        return {
            "kpi": "cache_hit_rate",
            "value": round(hits / total, 4),
            "status": "ok",
            "note": f"{hits}/{total} calls had cache hits",
        }
    except FileNotFoundError:
        return {
            "kpi": "cache_hit_rate",
            "value": None,
            "status": "not_instrumented",
            "note": "AGENT_RUN_LOG.jsonl not found",
        }
    except Exception as e:
        return {
            "kpi": "cache_hit_rate",
            "value": None,
            "status": "error",
            "note": str(e),
        }


if __name__ == "__main__":
    print(json.dumps(collect()))
