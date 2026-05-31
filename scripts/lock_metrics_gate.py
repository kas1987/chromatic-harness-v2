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
from pathlib import Path

_METRICS = Path(".agents/audits/locks/latest_lock_metrics.json")


def main() -> int:
    data: dict = {}
    if _METRICS.is_file():
        try:
            data = json.loads(_METRICS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    rate = float(data.get("timeout_rate", 0.0) or 0.0)
    p95 = float((data.get("wait_ms") or {}).get("p95", 0) or 0)
    total = int((data.get("event_counts") or {}).get("total", 0) or 0)
    print(f"LOCK_METRICS_SUMMARY timeout_rate={rate} p95_ms={p95} total={total}")

    thr = float(os.environ.get("CHROMATIC_LOCK_TIMEOUT_RATE_THRESHOLD", "0.05"))
    min_n = int(os.environ.get("CHROMATIC_LOCK_MIN_SAMPLE_SIZE", "20"))
    print(
        f"LOCK_GATE timeout_rate={rate} total={total} threshold={thr} min_sample={min_n}"
    )
    return 1 if (total >= min_n and rate > thr) else 0


if __name__ == "__main__":
    raise SystemExit(main())
