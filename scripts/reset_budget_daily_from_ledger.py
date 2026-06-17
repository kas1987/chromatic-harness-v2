#!/usr/bin/env python3
"""Reset budget/daily.jsonl from the authoritative ledger, then verify.

daily.jsonl is a derived rollup that was N-counted by the (now fixed)
bridge_today_to_daily re-append bug. ledger.jsonl is the source of truth
(one row per decision_id, real usd + ts). Rebuild deduped by decision_id,
test/mock excluded, real per-day timestamps preserved. Backs up first.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BUDGET = Path(__file__).resolve().parent.parent / "07_LOGS_AND_AUDIT" / "budget"
LEDGER = BUDGET / "ledger.jsonl"
DAILY = BUDGET / "daily.jsonl"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_test(row):
    cc = row.get("cost_center") or {}
    model = str(cc.get("model") or "")
    return cc.get("agent") == "test" or model.startswith("mock") or row.get("source") == "test"


def _classify_ledger_row(row: dict) -> dict:
    """Fill c_level/t_level inside cost_center from model name when absent.

    Returns the (possibly mutated) row. Existing non-null levels are preserved.
    """
    import sys as _sys
    from pathlib import Path as _Path

    _scripts = str(_Path(__file__).resolve().parent)
    if _scripts not in _sys.path:
        _sys.path.insert(0, _scripts)
    from token_level_inference import infer_levels  # type: ignore[import]

    cc = row.get("cost_center")
    if not isinstance(cc, dict):
        return row
    model = str(cc.get("model") or "")
    if not model:
        return row
    c_level = cc.get("c_level")
    t_level = cc.get("t_level")
    if c_level is not None and t_level is not None:
        return row
    inferred_c, inferred_t, _ = infer_levels(model)
    if c_level is None:
        cc["c_level"] = inferred_c
    if t_level is None:
        cc["t_level"] = inferred_t
    row["confidence"] = "inferred"
    return row


def main():
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    by_id, no_id = {}, []
    for r in rows:
        if is_test(r):
            continue
        did = r.get("decision_id")
        (by_id.__setitem__(did, r) if did else no_id.append(r))
    kept = list(by_id.values()) + no_id

    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_rows, total = [], 0.0
    for r in kept:
        ts = str(r.get("ts") or r.get("timestamp") or "")
        usd = float(r.get("usd") or 0.0)
        model = (r.get("cost_center") or {}).get("model") or "unknown"
        prefix = "today" if ts[:10] == today_prefix else "ledger"
        out_rows.append(
            {
                "timestamp": ts,
                "amount_usd": round(usd, 6),
                "source": f"{prefix}:{model}",
                "note": "" if r.get("confidence") == "known" else "unknown_usage",
                "decision_id": r.get("decision_id"),
            }
        )
        total += usd
    out_rows.sort(key=lambda x: x["timestamp"])

    for f in (DAILY, BUDGET / "forecast_latest.json", BUDGET / "monthly.json"):
        if f.is_file():
            shutil.copy2(f, f.with_suffix(f.suffix + f".{STAMP}.bak"))

    DAILY.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), encoding="utf-8")

    from collections import OrderedDict

    by_day = OrderedDict()
    for r in out_rows:
        by_day[r["timestamp"][:10]] = by_day.get(r["timestamp"][:10], 0.0) + r["amount_usd"]
    print(f"rebuilt daily.jsonl: {len(out_rows)} rows, total ${total:,.2f}")
    for d, v in by_day.items():
        print(f"  {d}: ${v:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
