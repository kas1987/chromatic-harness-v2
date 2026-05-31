#!/usr/bin/env python3
"""Print the lock-metrics summary and enforce the timeout-rate gate.

Replaces two fragile inline `python -c "..."` CI steps that broke under PowerShell
quoting on Windows. Reads `.agents/audits/locks/latest_lock_metrics.json` tolerantly
(a missing file means "no lock data" -> pass), prints a one-line summary, and exits 1
only when the timeout rate exceeds the threshold with a meaningful sample size.

Env:
  CHROMATIC_LOCK_TIMEOUT_RATE_THRESHOLD (default 0.05)
  CHROMATIC_LOCK_MIN_SAMPLE_SIZE        (default 20)
"""

from __future__ import annotations

import json
import os
from typing import Any
from pathlib import Path

_METRICS = Path(".agents/audits/locks/latest_lock_metrics.json")


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    # A MISSING file = no lock activity → fail open (pass). But a PRESENT file that is
    # corrupt/unreadable/non-dict means the rollup we just generated is broken — that's
    # a real regression, so FAIL the gate rather than silently passing with zeros. Nested
    # values and env vars are still cast defensively (data-quality within a valid report).
    data: dict = {}
    if _METRICS.is_file():
        try:
            loaded = json.loads(_METRICS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"LOCK_GATE FAIL: metrics file present but unreadable: {exc}")
            return 1
        if not isinstance(loaded, dict):
            print("LOCK_GATE FAIL: metrics root is not a JSON object")
            return 1
        data = loaded

    wait_ms = data.get("wait_ms") if isinstance(data.get("wait_ms"), dict) else {}
    counts = (
        data.get("event_counts") if isinstance(data.get("event_counts"), dict) else {}
    )
    rate = _num(data.get("timeout_rate"), 0.0)
    p95 = _num(wait_ms.get("p95"), 0.0)
    total = int(_num(counts.get("total"), 0))
    print(f"LOCK_METRICS_SUMMARY timeout_rate={rate} p95_ms={p95} total={total}")

    thr = _num(os.environ.get("CHROMATIC_LOCK_TIMEOUT_RATE_THRESHOLD"), 0.05)
    min_n = int(_num(os.environ.get("CHROMATIC_LOCK_MIN_SAMPLE_SIZE"), 20))
    print(
        f"LOCK_GATE timeout_rate={rate} total={total} threshold={thr} min_sample={min_n}"
    )
    return 1 if (total >= min_n and rate > thr) else 0


if __name__ == "__main__":
    raise SystemExit(main())
